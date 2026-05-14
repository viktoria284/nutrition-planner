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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base_class import Base
from app.models.constants import DEFAULT_FOOD_CATEGORY, FOOD_CATEGORIES, FOOD_CATEGORIES_SET
from app.models.enums import FoodSource, FoodStatus

FOOD_CATEGORY_SQL_VALUES = ", ".join(f"'{value}'" for value in FOOD_CATEGORIES)


class FoodItem(Base):
    __tablename__ = "food_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DEFAULT_FOOD_CATEGORY,
        server_default=text(f"'{DEFAULT_FOOD_CATEGORY}'"),
    )

    kcal: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    protein: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    fat: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    carbs: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    fiber: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
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

    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reports_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_listed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
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

    servings: Mapped[list["FoodServing"]] = relationship(
        "FoodServing",
        back_populates="food",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reports: Mapped[list["FoodReport"]] = relationship(
        "FoodReport",
        back_populates="food",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_food_items_name_not_blank"),
        CheckConstraint("(source != 'verified') OR owner_user_id IS NULL", name="ck_food_items_verified_owner_null"),
        CheckConstraint("kcal >= 0", name="ck_food_items_kcal_non_negative"),
        CheckConstraint("protein >= 0", name="ck_food_items_protein_non_negative"),
        CheckConstraint("fat >= 0", name="ck_food_items_fat_non_negative"),
        CheckConstraint("carbs >= 0", name="ck_food_items_carbs_non_negative"),
        CheckConstraint("fiber >= 0", name="ck_food_items_fiber_non_negative"),
        CheckConstraint("kcal <= 1000", name="ck_food_items_kcal_max"),
        CheckConstraint("protein <= 100", name="ck_food_items_protein_max"),
        CheckConstraint("fat <= 100", name="ck_food_items_fat_max"),
        CheckConstraint("carbs <= 100", name="ck_food_items_carbs_max"),
        CheckConstraint("fiber <= 100", name="ck_food_items_fiber_max"),
        CheckConstraint(
            f"category IN ({FOOD_CATEGORY_SQL_VALUES})",
            name="ck_food_items_category_allowed",
        ),
        Index("ix_food_items_name_lower", func.lower(name)),
        Index("ix_food_items_source_status_is_listed", source, status, is_listed),
    )

    @validates("name")
    def _validate_name(self, _key: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("FoodItem name cannot be empty")
        return normalized

    @validates("brand")
    def _validate_brand(self, _key: str, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @validates("category")
    def _validate_category(self, _key: str, value: str) -> str:
        normalized = value.strip()
        if normalized not in FOOD_CATEGORIES_SET:
            raise ValueError("Invalid food category")
        return normalized


class FoodServing(Base):
    __tablename__ = "food_servings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    food_id: Mapped[int] = mapped_column(
        ForeignKey("food_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    grams: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)

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

    food: Mapped[FoodItem] = relationship("FoodItem", back_populates="servings")

    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_food_servings_name_not_blank"),
        CheckConstraint("grams > 0", name="ck_food_servings_grams_positive"),
    )

    @validates("name")
    def _validate_name(self, _key: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("FoodServing name cannot be empty")
        return normalized


class FoodReport(Base):
    __tablename__ = "food_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    food_id: Mapped[int] = mapped_column(
        ForeignKey("food_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reporter_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    food: Mapped[FoodItem] = relationship("FoodItem", back_populates="reports")

    __table_args__ = (
        UniqueConstraint("food_id", "reporter_user_id", name="uq_food_reports_food_reporter"),
    )
