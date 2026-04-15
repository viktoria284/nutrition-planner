from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

PositiveDecimal = Annotated[Decimal, Field(gt=0)]


class PlanCreate(BaseModel):
    start_date: date
    days_count: Annotated[int, Field(ge=1, le=7)]
    meals_per_day: Annotated[int, Field(ge=2, le=6)]
    title: Annotated[str, Field(max_length=120)] | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class PlanAutogenerateRequest(BaseModel):
    start_date: date
    days_count: Annotated[int, Field(ge=1, le=7)]
    meals_per_day: Annotated[int, Field(ge=2, le=6)]
    profile_id: Annotated[int, Field(ge=1)] | None = None
    use_public_recipes: bool = True
    excluded_recipe_ids: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)
    excluded_food_ids: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)


class ReplacePlanSlotRequest(BaseModel):
    excluded_recipe_ids: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)
    excluded_food_ids: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)
    use_public_recipes: bool = True
    avoid_current_recipe: bool = True


class RegeneratePlanDayRequest(BaseModel):
    excluded_recipe_ids: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)
    excluded_food_ids: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)
    use_public_recipes: bool = True


class PlanSlotUpdate(BaseModel):
    recipe_id: Annotated[int, Field(ge=1)] | None = None
    servings_multiplier: PositiveDecimal | None = None
    pinned: bool | None = None

    @model_validator(mode="after")
    def validate_non_empty_payload(self) -> "PlanSlotUpdate":
        if len(self.model_fields_set) == 0:
            raise ValueError("at least one field must be provided")
        return self


class PlanSlotRead(BaseModel):
    id: int
    plan_id: int
    day_date: date
    slot_index: int
    recipe_id: int | None
    servings_multiplier: Decimal
    slot_kcal: Decimal
    slot_protein: Decimal
    slot_fat: Decimal
    slot_carbs: Decimal
    pinned: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NutritionTotalsRead(BaseModel):
    kcal: Decimal
    protein: Decimal
    fat: Decimal
    carbs: Decimal


class PlanDayRead(BaseModel):
    date: date
    totals: NutritionTotalsRead
    slots: list[PlanSlotRead]


class PlanRead(BaseModel):
    id: int
    owner_user_id: int
    profile_id: int | None
    profile_name: str | None
    start_date: date
    days_count: int
    meals_per_day: int
    title: str | None
    target_kcal: int | None
    target_protein: int | None
    target_fat: int | None
    target_carbs: int | None
    slots: list[PlanSlotRead]
    days: list[PlanDayRead]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlanAutogenerateResponse(PlanRead):
    pass


class PlanListItem(BaseModel):
    id: int
    owner_user_id: int
    profile_id: int | None
    start_date: date
    days_count: int
    meals_per_day: int
    title: str | None
    target_kcal: int | None
    target_protein: int | None
    target_fat: int | None
    target_carbs: int | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
