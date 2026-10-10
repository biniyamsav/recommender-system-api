from __future__ import annotations

from collections import defaultdict
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Product, User, UserEvent
from app.db.session import get_db
from app.main import app
from app.services import events
from app.services.user_service import get_user_profile_summary


class PipelineResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class PipelineDatabase:
    def __init__(self):
        self.users: dict[int, User] = {}
        self.products: dict[int, Product] = {}
        self.events: list[UserEvent] = []
        self.next_event_id = 1


class PipelineSession:
    def __init__(self, database: PipelineDatabase):
        self.database = database

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    def add(self, entity):
        if isinstance(entity, UserEvent):
            entity.id = self.database.next_event_id
            self.database.next_event_id += 1
            self.database.events.append(entity)

    async def commit(self):
        return None

    async def rollback(self):
        return None

    async def execute(self, statement):
        totals = defaultdict(lambda: {"view_seconds": 0.0, "purchase_usd": 0.0})
        user_id = next(iter(self.database.users))
        for event in self.database.events:
            if event.user_id != user_id:
                continue
            product = self.database.products.get(event.product_id)
            category = event.category or (product.category if product else None)
            if category is None:
                continue
            if event.event_type in {"product_view", "category_view"}:
                totals[category]["view_seconds"] += event.value
            elif event.event_type == "purchase":
                totals[category]["purchase_usd"] += event.value

        return PipelineResult(
            [
                (category, values["view_seconds"], values["purchase_usd"])
                for category, values in totals.items()
            ]
        )


class PipelineRedis:
    def __init__(self):
        self.values: dict[str, str] = {}

    async def delete(self, key: str):
        return int(self.values.pop(key, None) is not None)


@pytest.mark.asyncio
async def test_event_to_recommendation_pipeline(monkeypatch):
    database = PipelineDatabase()
    user = User(id=321, external_id="pipeline_user")
    product = Product(
        id=654,
        sku="PIPELINE-1",
        name="Test item",
        category="electronics",
        unit_price=19.99,
        is_active=True,
    )
    database.users[user.id] = user
    database.products[product.id] = product
    redis = PipelineRedis()
    cache_key = f"rec:user:{user.id}"
    redis.values[cache_key] = "stale"
    monkeypatch.setattr(events, "AsyncSessionLocal", lambda: PipelineSession(database))
    monkeypatch.setattr("app.db.redis.redis_client", redis)

    async def override_get_db() -> AsyncGenerator[PipelineSession, None]:
        yield PipelineSession(database)

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(
        "app.services.recommender.get_cached_data",
        lambda key: _async_return(None),
    )
    monkeypatch.setattr(
        "app.services.recommender.set_cached_data",
        lambda key, value, ttl=300: _async_return(None),
    )

    observed_profiles = []

    async def fake_generate_recommendations(
        db, user_id, user_profile, candidate_limit=50
    ):
        observed_profiles.append(user_profile)
        return {
            "prediction_id": 1,
            "latency_ms": 1.0,
            "recommendations": [{"product_id": product.id, "score": 0.9}],
        }

    monkeypatch.setattr(
        "app.api.routes.generate_recommendations", fake_generate_recommendations
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            post_response = await client.post(
                "/api/v1/events",
                json={
                    "user_id": user.id,
                    "event_type": "product_view",
                    "product_id": product.id,
                    "value": 37.5,
                },
            )
            assert post_response.status_code == 202
            assert cache_key not in redis.values

            profile = await get_user_profile_summary(
                PipelineSession(database), user.id
            )
            assert profile["electronics"] == {
                "view_seconds": 37.5,
                "purchase_usd": 0.0,
            }

            get_response = await client.get(
                f"/api/v1/recommendations/{user.id}"
            )

        assert get_response.status_code == 200
        assert observed_profiles == [profile]
        assert observed_profiles[0]["electronics"]["view_seconds"] == 37.5
    finally:
        app.dependency_overrides.pop(get_db, None)


async def _async_return(value):
    return value
