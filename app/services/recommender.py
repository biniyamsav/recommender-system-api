import time
from collections.abc import Awaitable, Callable
from typing import Any, Dict

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import ModelVersion, Prediction, Product, Recommendation
from app.db.redis import get_cached_data, set_cached_data
from app.services.groq_client import get_llm_reranked_scores

RecommendationGenerator = Callable[..., Awaitable[Dict[str, Any]]]


async def generate_recommendations(
    db: AsyncSession, user_id: int, user_profile: dict, candidate_limit: int = 50
) -> Dict[str, Any]:
    """
    Stage 1: Candidate retrieval from PostgreSQL.
    Stage 2: LLM reranking through the Groq client service.
    Stage 3: Persist prediction and scored recommendations atomically.
    """
    try:
        candidate_limit = max(int(candidate_limit), 1)
    except (TypeError, ValueError):
        candidate_limit = 50

    top_categories: list[str] = []
    if isinstance(user_profile, dict):
        top_categories = [
            str(category)
            for category in user_profile.keys()
            if isinstance(category, str)
        ]

    stmt = select(Product).where(Product.is_active == True)
    if top_categories:
        stmt = stmt.order_by(
            case((Product.category.in_(top_categories), 1), else_=2),
            Product.id.desc(),
        )
    else:
        stmt = stmt.order_by(Product.id.desc())
    stmt = stmt.limit(candidate_limit)

    result = await db.execute(stmt)
    candidates = result.scalars().all()

    product_list = [
        {"id": p.id, "name": p.name, "category": p.category, "price": float(p.unit_price)}
        for p in candidates
    ]

    start_time = time.time()
    recommended_items = await get_llm_reranked_scores(user_profile, product_list)
    latency_ms = (time.time() - start_time) * 1000

    mv_stmt = select(ModelVersion).where(ModelVersion.is_active == True)
    mv_result = await db.execute(mv_stmt)
    active_model = mv_result.scalars().first()

    prediction = Prediction(
        user_id=user_id,
        model_version_id=active_model.id if active_model else None,
        latency_ms=latency_ms,
    )
    db.add(prediction)
    await db.flush()

    for rank, item in enumerate(recommended_items, start=1):
        rec = Recommendation(
            prediction_id=prediction.id,
            product_id=item["product_id"],
            score=item["score"],
            rank_position=rank,
        )
        db.add(rec)

    await db.commit()
    await db.refresh(prediction)

    return {
        "prediction_id": prediction.id,
        "latency_ms": latency_ms,
        "total_scored": len(recommended_items),
        "recommendations": recommended_items,
    }


async def get_cached_recommendations(
    db: AsyncSession,
    user_id: int,
    user_profile: dict,
    limit: int = 50,
    ttl: int = settings.CACHE_EXPIRATION_SECONDS,
    recommendation_generator: RecommendationGenerator | None = None,
) -> Dict[str, Any]:
    """
    Cached wrapper around generate_recommendations.
    Checks Redis first; if missing, runs full DB + Groq pipeline and caches the result.
    """
    cache_key = f"rec:user:{user_id}"

    # 1. Check Redis Cache
    cached_recs = await get_cached_data(cache_key)
    if cached_recs:
        return cached_recs

    # 2. Pipeline Execution (PostgreSQL Retrieval + Groq Reranking + DB Persistence)
    generator = recommendation_generator or generate_recommendations
    recommendations = await generator(
        db=db,
        user_id=user_id,
        user_profile=user_profile,
        candidate_limit=limit,
    )

    # 3. Cache Results in Redis
    await set_cached_data(cache_key, recommendations, ttl=ttl)

    return recommendations


get_recommendations_for_user = get_cached_recommendations