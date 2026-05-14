from decimal import Decimal
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.models.constants import DEFAULT_FOOD_CATEGORY, FOOD_CATEGORIES_SET
from app.models.enums import FoodSource, FoodStatus


class FoodServingRead(BaseModel):
    id: int
    food_id: int
    name: str
    grams: Decimal

    class Config:
        from_attributes = True


class FoodItemRead(BaseModel):
    id: int
    name: str
    brand: str | None
    kcal: Decimal
    protein: Decimal
    fat: Decimal
    carbs: Decimal
    fiber: Decimal
    category: str
    source: FoodSource
    status: FoodStatus
    owner_user_id: int | None
    reports_count: int
    is_listed: bool

    class Config:
        from_attributes = True


class FoodItemWithServingsRead(FoodItemRead):
    servings: list[FoodServingRead]


KcalDecimal = Annotated[Decimal, Field(ge=0)]
MacroDecimal = Annotated[Decimal, Field(ge=0)]
PositiveDecimal = Annotated[Decimal, Field(gt=0)]

MAX_KCAL = Decimal("1000")
MAX_MACRO = Decimal("100")


class FoodItemCreate(BaseModel):
    name: str
    brand: str | None = None
    kcal: KcalDecimal
    protein: MacroDecimal
    fat: MacroDecimal
    carbs: MacroDecimal
    fiber: MacroDecimal = Decimal("0")
    category: str = DEFAULT_FOOD_CATEGORY

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("brand")
    @classmethod
    def validate_brand(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("kcal")
    @classmethod
    def validate_kcal_upper_bound(cls, value: Decimal) -> Decimal:
        if value > MAX_KCAL:
            raise ValueError("Калорийность должна быть ≤ 1000 ккал на 100 г.")
        return value

    @field_validator("protein")
    @classmethod
    def validate_protein_upper_bound(cls, value: Decimal) -> Decimal:
        if value > MAX_MACRO:
            raise ValueError("Белки/жиры/углеводы должны быть ≤ 100 на 100 г.")
        return value

    @field_validator("fat")
    @classmethod
    def validate_fat_upper_bound(cls, value: Decimal) -> Decimal:
        if value > MAX_MACRO:
            raise ValueError("Белки/жиры/углеводы должны быть ≤ 100 на 100 г.")
        return value

    @field_validator("carbs")
    @classmethod
    def validate_carbs_upper_bound(cls, value: Decimal) -> Decimal:
        if value > MAX_MACRO:
            raise ValueError("Белки/жиры/углеводы должны быть ≤ 100 на 100 г.")
        return value

    @field_validator("fiber")
    @classmethod
    def validate_fiber_upper_bound(cls, value: Decimal) -> Decimal:
        if value > MAX_MACRO:
            raise ValueError("Клетчатка должна быть ≤ 100 на 100 г.")
        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in FOOD_CATEGORIES_SET:
            raise ValueError("Invalid category")
        return normalized


class FoodItemUpdate(BaseModel):
    name: str | None = None
    brand: str | None = None
    kcal: KcalDecimal | None = None
    protein: MacroDecimal | None = None
    fat: MacroDecimal | None = None
    carbs: MacroDecimal | None = None
    fiber: MacroDecimal | None = None
    category: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("brand")
    @classmethod
    def validate_brand(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("kcal")
    @classmethod
    def validate_kcal_upper_bound(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if value > MAX_KCAL:
            raise ValueError("Калорийность должна быть ≤ 1000 ккал на 100 г.")
        return value

    @field_validator("protein")
    @classmethod
    def validate_protein_upper_bound(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if value > MAX_MACRO:
            raise ValueError("Белки/жиры/углеводы должны быть ≤ 100 на 100 г.")
        return value

    @field_validator("fat")
    @classmethod
    def validate_fat_upper_bound(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if value > MAX_MACRO:
            raise ValueError("Белки/жиры/углеводы должны быть ≤ 100 на 100 г.")
        return value

    @field_validator("carbs")
    @classmethod
    def validate_carbs_upper_bound(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if value > MAX_MACRO:
            raise ValueError("Белки/жиры/углеводы должны быть ≤ 100 на 100 г.")
        return value

    @field_validator("fiber")
    @classmethod
    def validate_fiber_upper_bound(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if value > MAX_MACRO:
            raise ValueError("Клетчатка должна быть ≤ 100 на 100 г.")
        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if normalized not in FOOD_CATEGORIES_SET:
            raise ValueError("Invalid category")
        return normalized


class FoodServingCreate(BaseModel):
    name: str
    grams: PositiveDecimal

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class FoodReportCreate(BaseModel):
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class FoodReportRead(BaseModel):
    id: int
    food_id: int
    reporter_user_id: int
    reason: str | None
    created_at: datetime

    class Config:
        from_attributes = True
