from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    interactions: Mapped[List["Interaction"]] = relationship(
        "Interaction", back_populates="user"
    )
    predictions: Mapped[List["Prediction"]] = relationship(
        "Prediction", back_populates="user"
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    # Relationships
    interactions: Mapped[List["Interaction"]] = relationship(
        "Interaction", back_populates="product"
    )
    recommendations: Mapped[List["Recommendation"]] = relationship(
        "Recommendation", back_populates="product"
    )


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_value: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="interactions")
    product: Mapped["Product"] = relationship("Product", back_populates="interactions")


class UserEvent(Base):
    __tablename__ = "user_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    product_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )

    user: Mapped["User"] = relationship("User")
    product: Mapped[Optional["Product"]] = relationship("Product")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    version_name: Mapped[str] = mapped_column(String(100), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(100), nullable=False)
    hyperparameters: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    metrics: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    # Relationships
    predictions: Mapped[List["Prediction"]] = relationship(
        "Prediction", back_populates="model_version"
    )


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_version_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="predictions")
    model_version: Mapped[Optional["ModelVersion"]] = relationship(
        "ModelVersion", back_populates="predictions"
    )
    recommendations: Mapped[List["Recommendation"]] = relationship(
        "Recommendation", back_populates="prediction", cascade="all, delete-orphan"
    )


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    prediction_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("predictions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    prediction: Mapped["Prediction"] = relationship(
        "Prediction", back_populates="recommendations"
    )
    product: Mapped["Product"] = relationship(
        "Product", back_populates="recommendations"
    )