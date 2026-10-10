import json
import logging
from typing import Optional, Any

from redis.asyncio import Redis

from app.core.config import settings

redis_client: Optional[Redis] = None
logger = logging.getLogger(__name__)

async def init_redis() -> None:
    """Initialize the Redis connection pool."""
    global redis_client
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

async def close_redis() -> None:
    """Close the Redis connection pool gracefully."""
    global redis_client
    if redis_client:
        client = redis_client
        redis_client = None
        await client.aclose()

async def get_cached_data(key: str) -> Optional[Any]:
    """Retrieve and deserialize JSON data from Redis."""
    if not redis_client:
        return None
    try:
        data = await redis_client.get(key)
        return json.loads(data) if data else None
    except Exception:
        logger.exception("Failed to read cached data for key %s", key)
        return None

async def set_cached_data(key: str, value: Any, ttl: int = settings.CACHE_EXPIRATION_SECONDS) -> None:
    """Serialize and cache data in Redis with a TTL."""
    if not redis_client:
        return
    try:
        await redis_client.set(key, json.dumps(value), ex=ttl)
    except Exception:
        logger.exception("Failed to write cached data for key %s", key)

async def delete_cached_data(key: str) -> None:
    """Delete a cached value, surfacing Redis failures to the caller."""
    if not redis_client:
        return
    await redis_client.delete(key)