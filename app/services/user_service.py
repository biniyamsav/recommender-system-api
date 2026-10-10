from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Product, UserEvent


async def get_user_profile_summary(db: AsyncSession, user_id: int) -> dict:
    """
    Aggregates user event history from PostgreSQL into a category summary dictionary.
    Calculates total viewing time (seconds) and monetary spend (USD) per category.
    """
    category = func.coalesce(UserEvent.category, Product.category)
    stmt = (
        select(
            category.label("category"),
            func.sum(
                case(
                    (UserEvent.event_type == "product_view", UserEvent.value),
                    (UserEvent.event_type == "category_view", UserEvent.value),
                    else_=0,
                )
            ).label("view_seconds"),
            func.sum(
                case(
                    (UserEvent.event_type == "purchase", UserEvent.value),
                    else_=0,
                )
            ).label("purchase_usd"),
        )
        .select_from(UserEvent)
        .outerjoin(Product, UserEvent.product_id == Product.id)
        .where(UserEvent.user_id == user_id, category.is_not(None))
        .group_by(category)
    )

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return {}

    return {
        category: {
            "view_seconds": float(views or 0.0),
            "purchase_usd": float(purchases or 0.0),
        }
        for category, views, purchases in rows
    }