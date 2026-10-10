from __future__ import annotations

import pytest

from app.main import app


@pytest.mark.asyncio
async def test_post_events_returns_202(async_client):
    response = await async_client.post(
        "/api/v1/events",
        json={
            "user_id": 123,
            "event_type": "product_view",
            "product_id": 42,
            "value": 12.5,
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert "Event received" in payload["message"]


@pytest.mark.asyncio
async def test_get_recommendations_returns_paginated_payload(async_client, monkeypatch):
    async def fake_summary(*args, **kwargs):
        return {"audio": {"view_seconds": 15.0, "purchase_usd": 45.0}}

    async def fake_generate(*args, **kwargs):
        return {
            "prediction_id": 98,
            "latency_ms": 12.4,
            "recommendations": [
                {"product_id": 1, "score": 0.90},
                {"product_id": 2, "score": 0.80},
                {"product_id": 3, "score": 0.70},
            ],
        }

    monkeypatch.setattr("app.api.routes.get_user_profile_summary", fake_summary)
    monkeypatch.setattr("app.api.routes.generate_recommendations", fake_generate)

    response = await async_client.get("/api/v1/recommendations/123?page=1&limit=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["prediction_id"] == 98
    assert payload["page"] == 1
    assert payload["limit"] == 2
    assert payload["total_items"] == 3
    assert len(payload["items"]) == 2
    assert payload["items"][0]["product_id"] == 1
