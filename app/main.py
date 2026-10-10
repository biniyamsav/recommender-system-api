from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.db.redis import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    try:
        yield
    finally:
        await close_redis()


app = FastAPI(title="Recommender Service", lifespan=lifespan)
app.include_router(router)
