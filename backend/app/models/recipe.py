from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base_class import Base
from app.models.enums import FoodSource, FoodStatus


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    servings_count: Mapped[int] = mapped_column(Integer, nullable=False)
    meal_types: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
    )
    source: Mapped[FoodSource] = mapped_column(
        SAEnum(FoodSource, name="food_source", native_enum=True),
        nullable=False,
        server_default=FoodSource.private.value,
    )
    status: Mapped[FoodStatus] = mapped_column(
        SAEnum(FoodStatus, name="food_status", native_enum=True),
        nullable=False,
        server_default=FoodStatus.draft.value,
    )
    is_listed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    reports_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        "RecipeIngredient",
        back_populates="recipe",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reports: Mapped[list["RecipeReport"]] = relationship(
        "RecipeReport",
        back_populates="recipe",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_recipes_name_not_blank"),
        CheckConstraint("servings_count >= 1", name="ck_recipes_servings_count_ge_1"),
        Index("ix_recipes_source_status_is_listed", source, status, is_listed),
    )

    @validates("name")
    def _validate_name(self, _key: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Recipe name cannot be empty")
        return normalized

    @validates("description")
    def _validate_description(self, _key: str, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    food_id: Mapped[int] = mapped_column(
        ForeignKey("food_items.id"),
        nullable=False,
        index=True,
    )
    grams: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    serving_id: Mapped[int | None] = mapped_column(
        ForeignKey("food_servings.id"),
        nullable=True,
    )
    multiplier: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    recipe: Mapped[Recipe] = relationship("Recipe", back_populates="ingredients")
    food: Mapped["FoodItem"] = relationship("FoodItem")

    __table_args__ = (
        CheckConstraint("grams > 0", name="ck_recipe_ingredients_grams_gt_0"),
    )


class RecipeReport(Base):
    __tablename__ = "recipe_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reporter_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    recipe: Mapped[Recipe] = relationship("Recipe", back_populates="reports")

    __table_args__ = (
        UniqueConstraint("recipe_id", "reporter_user_id", name="uq_recipe_reports_recipe_reporter"),
    )
