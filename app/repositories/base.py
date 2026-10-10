from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Base

# Type variable representing any SQLAlchemy model inheriting from Base
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: Any) -> Optional[ModelType]:
        """Fetch a single record by its primary key ID."""
        return await self.session.get(self.model, id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Fetch a list of records with pagination (skip/limit)."""
        statement = select(self.model).offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def create(self, instance: ModelType) -> ModelType:
        """Add a new record to the database session and commit."""
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance