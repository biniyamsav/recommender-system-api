from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import groq_client


@pytest.mark.asyncio
async def test_get_llm_reranked_scores_parses_valid_json(monkeypatch):
    response_payload = {
        "recommendations": [
            {"product_id": 1, "score": 0.91},
            {"product_id": 2, "score": 0.54},
        ]
    }
    fake_create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"recommendations": [{"product_id": 1, "score": 0.91}, {"product_id": 2, "score": 0.54}]}')
                )
            ]
        )
    )
    monkeypatch.setattr(groq_client.client.chat.completions, "create", fake_create)

    result = await groq_client.get_llm_reranked_scores(
        {"audio": {"view_seconds": 30.0, "purchase_usd": 10.0}},
        [{"product_id": 1}, {"product_id": 2}],
    )

    assert result == [{"product_id": 1, "score": 0.91}, {"product_id": 2, "score": 0.54}]
    assert fake_create.await_args.kwargs["model"] == groq_client.settings.GROQ_MODEL


@pytest.mark.asyncio
async def test_get_llm_reranked_scores_uses_fallback_on_exception(monkeypatch):
    monkeypatch.setattr(
        groq_client.client.chat.completions,
        "create",
        AsyncMock(side_effect=RuntimeError("network timeout")),
    )

    result = await groq_client.get_llm_reranked_scores(
        {"audio": {"view_seconds": 30.0, "purchase_usd": 10.0}},
        [{"product_id": 7}, {"product_id": 8}],
    )

    assert result == [
        {"product_id": 7, "score": 0.50},
        {"product_id": 8, "score": 0.50},
    ]


@pytest.mark.asyncio
async def test_get_llm_reranked_scores_uses_fallback_on_malformed_json(monkeypatch):
    fake_create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"recommendations": "not-a-list"}')
                )
            ]
        )
    )
    monkeypatch.setattr(groq_client.client.chat.completions, "create", fake_create)

    result = await groq_client.get_llm_reranked_scores(
        {"audio": {"view_seconds": 30.0, "purchase_usd": 10.0}},
        [{"product_id": 11}, {"product_id": 12}],
    )

    assert result == [
        {"product_id": 11, "score": 0.50},
        {"product_id": 12, "score": 0.50},
    ]


@pytest.mark.asyncio
async def test_get_llm_reranked_scores_filters_hallucinations_and_clamps(monkeypatch):
    fake_create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"recommendations": [{"product_id": 1, "score": 1.5}, {"product_id": 99, "score": 0.8}, {"product_id": 2, "score": -0.4}]}'
                    )
                )
            ]
        )
    )
    monkeypatch.setattr(groq_client.client.chat.completions, "create", fake_create)

    result = await groq_client.get_llm_reranked_scores(
        {},
        [{"id": 1}, {"id": 2}],
    )

    assert result == [
        {"product_id": 1, "score": 1.0},
        {"product_id": 2, "score": 0.0},
    ]
