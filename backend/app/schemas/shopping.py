from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.constants import DEFAULT_FOOD_CATEGORY, FOOD_CATEGORIES_SET

PositiveDecimal = Annotated[Decimal, Field(gt=0)]


class ShoppingListSourceRead(BaseModel):
    id: int
    shopping_list_id: int
    plan_id: int
    date_from: date | None
    date_to: date | None
    created_at: datetime

    class Config:
        from_attributes = True


class ShoppingListItemRead(BaseModel):
    id: int
    shopping_list_id: int
    food_id: int | None
    name_snapshot: str
    category: str
    item_type: str
    planned_grams: Decimal | None
    adjusted_grams: Decimal | None
    effective_grams: Decimal | None
    unit: str
    checked: bool
    excluded: bool
    in_pantry_section: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class ShoppingListRead(BaseModel):
    id: int
    owner_user_id: int
    title: str
    status: str
    source_type: str
    source_signature: str | None
    is_outdated: bool
    generated_at: datetime
    created_at: datetime
    updated_at: datetime
    sources: list[ShoppingListSourceRead]
    items: list[ShoppingListItemRead]


class ShoppingListSummaryRead(BaseModel):
    id: int
    owner_user_id: int
    title: str
    status: str
    source_type: str
    source_signature: str | None
    is_outdated: bool
    generated_at: datetime
    created_at: datetime
    updated_at: datetime
    source_plan_ids: list[int]
    items_total: int


class ShoppingListCreateFromPlanRequest(BaseModel):
    plan_id: Annotated[int, Field(ge=1)]
    title: Annotated[str, Field(max_length=255)] | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ShoppingListMergeRequest(BaseModel):
    shopping_list_ids: list[Annotated[int, Field(ge=1)]]
    title: Annotated[str, Field(max_length=255)] | None = None

    @field_validator("shopping_list_ids")
    @classmethod
    def validate_list_ids(cls, value: list[int]) -> list[int]:
        if len(value) < 2:
            raise ValueError("at least two shopping lists are required")
        if len(set(value)) != len(value):
            raise ValueError("shopping list ids must be unique")
        return value

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ShoppingListBulkDeleteRequest(BaseModel):
    shopping_list_ids: list[Annotated[int, Field(ge=1)]]

    @field_validator("shopping_list_ids")
    @classmethod
    def validate_list_ids(cls, value: list[int]) -> list[int]:
        if len(value) == 0:
            raise ValueError("at least one shopping list is required")
        return value


class ShoppingListBulkDeleteResponse(BaseModel):
    deleted_count: int


class ShoppingListItemUpdate(BaseModel):
    checked: bool | None = None
    adjusted_grams: PositiveDecimal | None = None
    excluded: bool | None = None
    in_pantry_section: bool | None = None
    category: str | None = None
    name_snapshot: Annotated[str, Field(max_length=255)] | None = None
    unit: Annotated[str, Field(max_length=32)] | None = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if normalized not in FOOD_CATEGORIES_SET:
            raise ValueError("Invalid category")
        return normalized

    @field_validator("name_snapshot")
    @classmethod
    def validate_name_snapshot(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("name_snapshot cannot be empty")
        return normalized

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("unit cannot be empty")
        return normalized

    @model_validator(mode="after")
    def validate_non_empty_payload(self) -> "ShoppingListItemUpdate":
        if len(self.model_fields_set) == 0:
            raise ValueError("at least one field must be provided")
        return self


class ShoppingManualItemCreate(BaseModel):
    name: Annotated[str, Field(max_length=255)]
    category: str = DEFAULT_FOOD_CATEGORY
    unit: Annotated[str, Field(max_length=32)] = "g"
    adjusted_grams: PositiveDecimal | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in FOOD_CATEGORIES_SET:
            raise ValueError("Invalid category")
        return normalized

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("unit cannot be empty")
        return normalized
