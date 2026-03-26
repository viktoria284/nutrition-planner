from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class ShoppingOverride(Base):
    __tablename__ = "shopping_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    food_id: Mapped[int] = mapped_column(
        ForeignKey("food_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    checked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    excluded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    adjusted_grams: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 2),
        nullable=True,
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

    plan: Mapped["Plan"] = relationship("Plan")
    food: Mapped["FoodItem"] = relationship("FoodItem")

    __table_args__ = (
        UniqueConstraint("plan_id", "food_id", name="uq_shopping_overrides_plan_food"),
        CheckConstraint(
            "adjusted_grams IS NULL OR adjusted_grams > 0",
            name="ck_shopping_overrides_adjusted_grams_gt_0",
        ),
    )


class ShoppingManualItem(Base):
    __tablename__ = "shopping_manual_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    grams: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 2),
        nullable=True,
    )
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    checked: Mapped[bool] = mapped_column(
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

    plan: Mapped["Plan"] = relationship("Plan")

    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_shopping_manual_items_name_not_blank"),
        CheckConstraint("grams IS NULL OR grams > 0", name="ck_shopping_manual_items_grams_gt_0"),
    )
