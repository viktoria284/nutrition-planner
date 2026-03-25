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

    __table_args__ = (
        UniqueConstraint("plan_id", "day_date", "slot_index", name="uq_plan_slots_plan_day_slot"),
        CheckConstraint("slot_index >= 0", name="ck_plan_slots_slot_index_ge_0"),
        CheckConstraint("servings_multiplier > 0", name="ck_plan_slots_servings_multiplier_gt_0"),
        Index("ix_plan_slots_plan_id_day_date", plan_id, day_date),
    )
