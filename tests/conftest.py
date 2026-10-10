from __future__ import annotations

from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.db.session import get_db
from app.services import events


class MockAsyncSession:
    async def commit(self):
        return None

    async def execute(self, *args, **kwargs):
        return None

    async def flush(self):
        return None

    async def refresh(self, *args, **kwargs):
        return None

    async def rollback(self):
        return None

    def add(self, *args, **kwargs):
        return None


class MockBackgroundSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None

    def add(self, *args, **kwargs):
        return None


async def override_get_db() -> AsyncGenerator[MockAsyncSession, None]:
    yield MockAsyncSession()


@pytest.fixture
async def async_client(monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(events, "AsyncSessionLocal", MockBackgroundSession)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()
