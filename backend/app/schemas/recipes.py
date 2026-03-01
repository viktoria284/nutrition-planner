from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

ALLOWED_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}
MealTypes = Annotated[list[str], Field(min_length=1)]


class RecipeCreate(BaseModel):
    name: str
    description: str | None = None
    servings_count: Annotated[int, Field(ge=1)]
    meal_types: MealTypes

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("meal_types")
    @classmethod
    def validate_meal_types(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            item_normalized = item.strip().lower()
            if item_normalized not in ALLOWED_MEAL_TYPES:
                raise ValueError("invalid meal type")
            if item_normalized in seen:
                raise ValueError("duplicate meal type")
            seen.add(item_normalized)
            normalized.append(item_normalized)
        return normalized


class RecipeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    servings_count: Annotated[int, Field(ge=1)] | None = None
    meal_types: list[str] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("meal_types")
    @classmethod
    def validate_meal_types(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if len(value) == 0:
            raise ValueError("meal types cannot be empty")

        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            item_normalized = item.strip().lower()
            if item_normalized not in ALLOWED_MEAL_TYPES:
                raise ValueError("invalid meal type")
            if item_normalized in seen:
                raise ValueError("duplicate meal type")
            seen.add(item_normalized)
            normalized.append(item_normalized)
        return normalized


class RecipeRead(BaseModel):
    id: int
    owner_user_id: int
    name: str
    description: str | None
    servings_count: int
    meal_types: list[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
