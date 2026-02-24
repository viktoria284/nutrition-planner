from typing import Annotated
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

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
    source: FoodSource
    status: FoodStatus
    owner_user_id: int | None

    class Config:
        from_attributes = True


class FoodItemWithServingsRead(FoodItemRead):
    servings: list[FoodServingRead]


KcalDecimal = Annotated[Decimal, Field(ge=0, le=2000)]
MacroDecimal = Annotated[Decimal, Field(ge=0, le=200)]


class FoodItemCreate(BaseModel):
    name: str
    brand: str | None = None
    kcal: KcalDecimal
    protein: MacroDecimal
    fat: MacroDecimal
    carbs: MacroDecimal

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


class FoodItemUpdate(BaseModel):
    name: str | None = None
    brand: str | None = None
    kcal: KcalDecimal | None = None
    protein: MacroDecimal | None = None
    fat: MacroDecimal | None = None
    carbs: MacroDecimal | None = None

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
