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
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base_class import Base
from app.models.constants import (
    DEFAULT_FOOD_CATEGORY,
    DEFAULT_SHOPPING_LIST_SOURCE_TYPE,
    DEFAULT_SHOPPING_LIST_STATUS,
    FOOD_CATEGORIES,
    FOOD_CATEGORIES_SET,
    SHOPPING_ITEM_TYPES,
    SHOPPING_LIST_SOURCE_TYPES,
    SHOPPING_LIST_STATUSES,
)

FOOD_CATEGORY_SQL_VALUES = ", ".join(f"'{value}'" for value in FOOD_CATEGORIES)
SHOPPING_ITEM_TYPE_SQL_VALUES = ", ".join(f"'{value}'" for value in SHOPPING_ITEM_TYPES)
SHOPPING_LIST_STATUS_SQL_VALUES = ", ".join(f"'{value}'" for value in SHOPPING_LIST_STATUSES)
SHOPPING_LIST_SOURCE_SQL_VALUES = ", ".join(f"'{value}'" for value in SHOPPING_LIST_SOURCE_TYPES)


class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DEFAULT_SHOPPING_LIST_STATUS,
        server_default=text(f"'{DEFAULT_SHOPPING_LIST_STATUS}'"),
    )
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DEFAULT_SHOPPING_LIST_SOURCE_TYPE,
        server_default=text(f"'{DEFAULT_SHOPPING_LIST_SOURCE_TYPE}'"),
    )
    source_signature: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_outdated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
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

    sources: Mapped[list["ShoppingListSource"]] = relationship(
        "ShoppingListSource",
        back_populates="shopping_list",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    items: Mapped[list["ShoppingListItem"]] = relationship(
        "ShoppingListItem",
        back_populates="shopping_list",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_shopping_lists_title_not_blank"),
        CheckConstraint(
            f"status IN ({SHOPPING_LIST_STATUS_SQL_VALUES})",
            name="ck_shopping_lists_status_allowed",
        ),
        CheckConstraint(
            f"source_type IN ({SHOPPING_LIST_SOURCE_SQL_VALUES})",
            name="ck_shopping_lists_source_type_allowed",
        ),
    )

    @validates("title")
    def _validate_title(self, _key: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("ShoppingList title cannot be empty")
        return normalized

    @validates("status")
    def _validate_status(self, _key: str, value: str) -> str:
        normalized = value.strip()
        if normalized not in SHOPPING_LIST_STATUSES:
            raise ValueError("Invalid shopping list status")
        return normalized

    @validates("source_type")
    def _validate_source_type(self, _key: str, value: str) -> str:
        normalized = value.strip()
        if normalized not in SHOPPING_LIST_SOURCE_TYPES:
            raise ValueError("Invalid shopping list source type")
        return normalized


class ShoppingListSource(Base):
    __tablename__ = "shopping_list_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shopping_list_id: Mapped[int] = mapped_column(
        ForeignKey("shopping_lists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    shopping_list: Mapped[ShoppingList] = relationship("ShoppingList", back_populates="sources")
    plan: Mapped["Plan"] = relationship("Plan")


class ShoppingListItem(Base):
    __tablename__ = "shopping_list_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shopping_list_id: Mapped[int] = mapped_column(
        ForeignKey("shopping_lists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    food_id: Mapped[int | None] = mapped_column(
        ForeignKey("food_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DEFAULT_FOOD_CATEGORY,
        server_default=text(f"'{DEFAULT_FOOD_CATEGORY}'"),
    )
    item_type: Mapped[str] = mapped_column(String(16), nullable=False)
    planned_grams: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    adjusted_grams: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="g",
        server_default=text("'g'"),
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
    in_pantry_section: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
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

    shopping_list: Mapped[ShoppingList] = relationship("ShoppingList", back_populates="items")
    food: Mapped["FoodItem | None"] = relationship("FoodItem")

    __table_args__ = (
        CheckConstraint("length(trim(name_snapshot)) > 0", name="ck_shopping_list_items_name_not_blank"),
        CheckConstraint(
            f"category IN ({FOOD_CATEGORY_SQL_VALUES})",
            name="ck_shopping_list_items_category_allowed",
        ),
        CheckConstraint(
            f"item_type IN ({SHOPPING_ITEM_TYPE_SQL_VALUES})",
            name="ck_shopping_list_items_item_type_allowed",
        ),
        CheckConstraint("planned_grams IS NULL OR planned_grams > 0", name="ck_shopping_list_items_planned_grams_gt_0"),
        CheckConstraint(
            "adjusted_grams IS NULL OR adjusted_grams > 0",
            name="ck_shopping_list_items_adjusted_grams_gt_0",
        ),
        CheckConstraint("length(trim(unit)) > 0", name="ck_shopping_list_items_unit_not_blank"),
        Index("ix_shopping_list_items_list_sort", "shopping_list_id", "sort_order", "id"),
    )

    @validates("name_snapshot")
    def _validate_name_snapshot(self, _key: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("ShoppingListItem name_snapshot cannot be empty")
        return normalized

    @validates("category")
    def _validate_category(self, _key: str, value: str) -> str:
        normalized = value.strip()
        if normalized not in FOOD_CATEGORIES_SET:
            raise ValueError("Invalid shopping item category")
        return normalized

    @validates("item_type")
    def _validate_item_type(self, _key: str, value: str) -> str:
        normalized = value.strip()
        if normalized not in SHOPPING_ITEM_TYPES:
            raise ValueError("Invalid shopping item type")
        return normalized

    @validates("unit")
    def _validate_unit(self, _key: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("ShoppingListItem unit cannot be empty")
        return normalized
