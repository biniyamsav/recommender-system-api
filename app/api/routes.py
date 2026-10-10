from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.events import process_event_in_background
from app.services.recommender import (
    generate_recommendations,
    get_cached_recommendations,
)
from app.services.user_service import get_user_profile_summary

router = APIRouter(prefix="/api/v1", tags=["recommendations"])


class EventPayload(BaseModel):
    user_id: int
    event_type: Literal["product_view", "category_view", "purchase"]
    product_id: Optional[int] = None
    category: Optional[str] = None
    value: float = Field(default=0.0, ge=0.0)


@router.post("/events", status_code=status.HTTP_202_ACCEPTED)
async def record_event(
    payload: EventPayload,
    background_tasks: BackgroundTasks,
):
    """
    Accepts event payload, validates parameters, offloads persistence and cache
    invalidation to background execution, and responds immediately.
    """
    background_tasks.add_task(
        process_event_in_background,
        user_id=payload.user_id,
        payload=payload.model_dump(),
    )

    return {
        "status": "queued",
        "message": "Event received and queued for processing.",
    }


@router.get("/recommendations/{user_id}")
async def get_recommendations(
    user_id: int,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    user_profile = await get_user_profile_summary(db, user_id)
    rec_result = await get_cached_recommendations(
        db=db,
        user_id=user_id,
        user_profile=user_profile,
        limit=50,
        recommendation_generator=generate_recommendations,
    )

    items = rec_result["recommendations"]
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated = items[start_idx:end_idx]

    return {
        "prediction_id": rec_result["prediction_id"],
        "latency_ms": rec_result["latency_ms"],
        "page": page,
        "limit": limit,
        "total_items": len(items),
        "items": paginated,
    }