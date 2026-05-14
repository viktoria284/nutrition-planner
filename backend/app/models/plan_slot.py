from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class PlanSlot(Base):
    __tablename__ = "plan_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_date: Mapped[date] = mapped_column(Date, nullable=False)
    slot_index: Mapped[int] = mapped_column(Integer, nullable=False)
    recipe_id: Mapped[int | None] = mapped_column(
        ForeignKey("recipes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    servings_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(8, 3),
        nullable=False,
        default=Decimal("1"),
        server_default=text("1"),
    )
    pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

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

    plan: Mapped["Plan"] = relationship("Plan", back_populates="slots")
    recipe: Mapped["Recipe"] = relationship("Recipe")
    ingredient_overrides: Mapped[list["PlanSlotIngredientOverride"]] = relationship(
        "PlanSlotIngredientOverride",
        back_populates="slot",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("plan_id", "day_date", "slot_index", name="uq_plan_slots_plan_day_slot"),
        CheckConstraint("slot_index >= 0", name="ck_plan_slots_slot_index_ge_0"),
        CheckConstraint("servings_multiplier > 0", name="ck_plan_slots_servings_multiplier_gt_0"),
        Index("ix_plan_slots_plan_id_day_date", plan_id, day_date),
    )


class PlanSlotIngredientOverride(Base):
    __tablename__ = "plan_slot_ingredient_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot_id: Mapped[int] = mapped_column(
        ForeignKey("plan_slots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipe_ingredient_id: Mapped[int | None] = mapped_column(
        ForeignKey("recipe_ingredients.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    food_id: Mapped[int | None] = mapped_column(
        ForeignKey("food_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    grams: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    is_excluded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    is_manual: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
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

    slot: Mapped["PlanSlot"] = relationship("PlanSlot", back_populates="ingredient_overrides")
    recipe_ingredient: Mapped["RecipeIngredient | None"] = relationship("RecipeIngredient")
    food: Mapped["FoodItem | None"] = relationship("FoodItem")

    __table_args__ = (
        UniqueConstraint(
            "slot_id",
            "recipe_ingredient_id",
            name="uq_slot_ingredient_overrides_slot_recipe_ingredient",
        ),
        CheckConstraint(
            "grams IS NULL OR grams > 0",
            name="ck_slot_ingredient_overrides_grams_gt_0",
        ),
    )
