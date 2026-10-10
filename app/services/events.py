from app.db.database import AsyncSessionLocal
from app.db.models import UserEvent
from app.db import redis as redis_service


async def process_event_in_background(user_id: int, payload: dict) -> None:
    """
    Executes as a background task:
    1. Persists event to PostgreSQL using an isolated session.
    2. Invalidates the user's cached recommendations in Redis.
    """
    async with AsyncSessionLocal() as db:
        try:
            event = UserEvent(
                user_id=user_id,
                event_type=payload.get("event_type"),
                product_id=payload.get("product_id"),
                category=payload.get("category"),
                value=payload.get("value", 0.0),
            )
            db.add(event)
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    await redis_service.delete_cached_data(f"rec:user:{user_id}")