from datetime import datetime
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import FoodSource, FoodStatus

ALLOWED_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}
MealTypes = Annotated[list[str], Field(min_length=1)]
PositiveDecimal = Annotated[Decimal, Field(gt=0)]
CookTimeMinutes = Annotated[int, Field(ge=1, le=1440)]


def _normalize_meal_types(value: list[str]) -> list[str]:
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


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _validate_image_url(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("image_url must be a valid http/https URL")
    return normalized


class RecipeCreate(BaseModel):
    name: str
    description: str | None = None
    instructions: str | None = None
    image_url: str | None = None
    servings_count: Annotated[int, Field(ge=1)]
    meal_types: MealTypes
    cook_time_minutes: CookTimeMinutes | None = None

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
        return _normalize_optional_text(value)

    @field_validator("instructions")
    @classmethod
    def validate_instructions(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value: str | None) -> str | None:
        return _validate_image_url(value)

    @field_validator("meal_types")
    @classmethod
    def validate_meal_types(cls, value: list[str]) -> list[str]:
        return _normalize_meal_types(value)


class RecipeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    instructions: str | None = None
    image_url: str | None = None
    servings_count: Annotated[int, Field(ge=1)] | None = None
    meal_types: list[str] | None = None
    cook_time_minutes: CookTimeMinutes | None = None

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
        return _normalize_optional_text(value)

    @field_validator("instructions")
    @classmethod
    def validate_instructions(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value: str | None) -> str | None:
        return _validate_image_url(value)

    @field_validator("meal_types")
    @classmethod
    def validate_meal_types(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if len(value) == 0:
            raise ValueError("meal types cannot be empty")
        return _normalize_meal_types(value)


class RecipeIngredientCreate(BaseModel):
    food_id: int
    grams: PositiveDecimal | None = None
    serving_id: int | None = None
    multiplier: PositiveDecimal | None = None

    @model_validator(mode="after")
    def validate_measurement_mode(self) -> "RecipeIngredientCreate":
        has_grams = self.grams is not None
        has_serving = self.serving_id is not None

        if not has_grams and not has_serving:
            raise ValueError("provide grams or serving_id")

        if has_serving and self.multiplier is None:
            raise ValueError("multiplier is required when serving_id is provided")

        return self


class RecipeIngredientUpdate(BaseModel):
    food_id: int | None = None
    grams: PositiveDecimal | None = None
    serving_id: int | None = None
    multiplier: PositiveDecimal | None = None

    @model_validator(mode="after")
    def validate_non_empty_payload(self) -> "RecipeIngredientUpdate":
        if len(self.model_fields_set) == 0:
            raise ValueError("at least one field must be provided")

        if "grams" in self.model_fields_set and self.grams is None:
            raise ValueError("grams must be greater than 0")

        if "serving_id" in self.model_fields_set and self.serving_id is not None and self.multiplier is None:
            raise ValueError("multiplier is required when serving_id is provided")

        if "multiplier" in self.model_fields_set and self.multiplier is not None:
            has_serving_context = self.serving_id is not None or "serving_id" not in self.model_fields_set
            if not has_serving_context:
                raise ValueError("serving_id is required when multiplier is provided")

        return self


class RecipeReportCreate(BaseModel):
    reason: str | None = None
    comment: str | None = None

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("comment")
    @classmethod
    def validate_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class RecipeIngredientFoodRead(BaseModel):
    id: int
    name: str
    brand: str | None = None

    class Config:
        from_attributes = True


class RecipeIngredientRead(BaseModel):
    id: int
    recipe_id: int
    food_id: int
    grams: Decimal
    serving_id: int | None = None
    multiplier: Decimal | None = None
    food: RecipeIngredientFoodRead | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecipeStepRead(BaseModel):
    id: int
    recipe_id: int
    position: int
    text: str
    note: str | None = None
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecipeStepInput(BaseModel):
    id: int | None = None
    position: Annotated[int, Field(ge=1)] | None = None
    text: str
    note: str | None = None

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("text cannot be empty")
        return normalized

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)


class RecipeStepsReplace(BaseModel):
    steps: list[RecipeStepInput] = Field(default_factory=list)


class RecipeRead(BaseModel):
    id: int
    owner_user_id: int
    name: str
    description: str | None
    instructions: str | None
    image_url: str | None
    servings_count: int
    meal_types: list[str]
    cook_time_minutes: int | None
    source: FoodSource
    status: FoodStatus
    reports_count: int
    is_listed: bool
    ingredients: list[RecipeIngredientRead] = Field(default_factory=list)
    steps: list[RecipeStepRead] = Field(default_factory=list)
    total_grams: Decimal
    total_kcal: Decimal
    total_protein: Decimal
    total_fat: Decimal
    total_carbs: Decimal
    per_serving_kcal: Decimal
    per_serving_protein: Decimal
    per_serving_fat: Decimal
    per_serving_carbs: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecipeNoteRead(BaseModel):
    note: str | None


class RecipeNoteUpsert(BaseModel):
    note: str

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("note cannot be blank")
        return normalized
