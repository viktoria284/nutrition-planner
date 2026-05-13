from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.models.constants import FOOD_CATEGORIES_SET

TargetKcal = Annotated[int, Field(ge=0, le=20000)]
TargetGrams = Annotated[int, Field(ge=0, le=2000)]
CookTimeMinutes = Annotated[int, Field(ge=1, le=1440)]


def _normalize_food_ids(value: list[int] | None) -> list[int]:
    if not value:
        return []
    return sorted(set(value))


def _normalize_categories(value: list[str] | None) -> list[str]:
    if not value:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        category = item.strip()
        if not category:
            continue
        if category not in FOOD_CATEGORIES_SET:
            raise ValueError("invalid food category")
        if category in seen:
            continue
        seen.add(category)
        normalized.append(category)
    return normalized


class ProfileCreate(BaseModel):
    name: str
    target_kcal: TargetKcal | None = None
    target_protein: TargetGrams | None = None
    target_fat: TargetGrams | None = None
    target_carbs: TargetGrams | None = None
    excluded_food_ids: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)
    preferred_food_ids: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)
    preferred_categories: list[str] = Field(default_factory=list)
    max_cook_time_minutes: CookTimeMinutes | None = None

    @field_validator("excluded_food_ids", "preferred_food_ids")
    @classmethod
    def validate_food_ids(cls, value: list[int]) -> list[int]:
        return _normalize_food_ids(value)

    @field_validator("preferred_categories")
    @classmethod
    def validate_preferred_categories(cls, value: list[str]) -> list[str]:
        return _normalize_categories(value)


class ProfileUpdate(BaseModel):
    name: str | None = None
    target_kcal: TargetKcal | None = None
    target_protein: TargetGrams | None = None
    target_fat: TargetGrams | None = None
    target_carbs: TargetGrams | None = None
    excluded_food_ids: list[Annotated[int, Field(ge=1)]] | None = None
    preferred_food_ids: list[Annotated[int, Field(ge=1)]] | None = None
    preferred_categories: list[str] | None = None
    max_cook_time_minutes: CookTimeMinutes | None = None

    @field_validator("excluded_food_ids", "preferred_food_ids")
    @classmethod
    def validate_food_ids(cls, value: list[int] | None) -> list[int]:
        return _normalize_food_ids(value)

    @field_validator("preferred_categories")
    @classmethod
    def validate_preferred_categories(cls, value: list[str] | None) -> list[str]:
        return _normalize_categories(value)


class ProfileOut(BaseModel):
    id: int
    user_id: int
    name: str
    target_kcal: int | None
    target_protein: int | None
    target_fat: int | None
    target_carbs: int | None
    excluded_food_ids: list[int] = Field(default_factory=list)
    preferred_food_ids: list[int] = Field(default_factory=list)
    preferred_categories: list[str] = Field(default_factory=list)
    max_cook_time_minutes: int | None

    class Config:
        from_attributes = True
