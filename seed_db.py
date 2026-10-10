import asyncio
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.models import Base, Interaction, ModelVersion, Product, User

NUM_USERS = 50
NUM_PRODUCTS = 20
NUM_INTERACTIONS = 200

CATEGORIES = [
    "electronics",
    "footwear",
    "wearables",
    "apparel",
    "home_appliances",
    "books",
    "sports_outdoors",
    "beauty",
]

EVENT_TYPES = ["product_view", "category_view", "purchase"]
EVENT_WEIGHTS = [0.65, 0.20, 0.15]


def get_db_url_for_local_run() -> str:
    url = settings.DATABASE_URL
    if "@db:" in url:
        return url.replace("@db:", "@localhost:")
    return url


async def seed_database() -> None:
    db_url = get_db_url_for_local_run()
    engine = create_async_engine(db_url, echo=False)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("TRUNCATE TABLE recommendations, predictions, interactions, products, users, model_versions RESTART IDENTITY CASCADE;"))

    async with SessionLocal() as session:
        print("Seeding model version...")
        model_version = ModelVersion(
            version_name="llama-3.3-70b-versatile",
            algorithm="LLM-Reranker",
            hyperparameters={"temperature": 0.2, "top_p": 0.9},
            metrics={"precision_at_3": 0.85},
            is_active=True,
        )
        session.add(model_version)
        await session.flush()

        print(f"Seeding {NUM_PRODUCTS} products...")
        products = []
        for i in range(1, NUM_PRODUCTS + 1):
            product = Product(
                sku=f"SKU-{i:04d}",
                name=f"{random.choice(CATEGORIES).title()} Item {i}",
                category=random.choice(CATEGORIES),
                unit_price=round(random.uniform(15.0, 499.99), 2),
                is_active=True,
            )
            session.add(product)
            products.append(product)
        await session.flush()

        print(f"Seeding {NUM_USERS} users...")
        users = []
        for i in range(1, NUM_USERS + 1):
            user = User(external_id=f"user_{i:04d}", is_active=True)
            session.add(user)
            users.append(user)
        await session.flush()

        print(f"Seeding {NUM_INTERACTIONS} interactions...")
        now = datetime.now(timezone.utc)
        for _ in range(NUM_INTERACTIONS):
            user = random.choice(users)
            product = random.choice(products)
            event_type = random.choices(EVENT_TYPES, weights=EVENT_WEIGHTS)[0]
            interaction = Interaction(
                user_id=user.id,
                product_id=product.id,
                event_type=event_type,
                event_value=round(random.uniform(1.0, 180.0), 2)
                if event_type != "purchase"
                else round(random.uniform(10.0, 300.0), 2),
                session_id=f"session_{random.randint(1, 500)}",
                created_at=now - timedelta(days=random.randint(0, 30), minutes=random.randint(0, 1439)),
            )
            session.add(interaction)

        await session.commit()

    await engine.dispose()
    print("Dummy data seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed_database())
