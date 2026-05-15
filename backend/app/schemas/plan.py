from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PositiveDecimal = Annotated[Decimal, Field(gt=0)]
AllowedBatchCookingDays = Annotated[int, Field(ge=1, le=3)]


class BatchCookingPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    breakfast: AllowedBatchCookingDays | None = None
    lunch: AllowedBatchCookingDays | None = None
    dinner: AllowedBatchCookingDays | None = None
    snack: AllowedBatchCookingDays | None = None


class PlanCreate(BaseModel):
    start_date: date
    days_count: Annotated[int, Field(ge=1, le=7)]
    meals_per_day: Annotated[int, Field(ge=2, le=6)]
    profile_id: Annotated[int, Field(ge=1)]
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
    title: Annotated[str, Field(max_length=120)] | None = None
    use_public_recipes: bool = True
    excluded_recipe_ids: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)
    excluded_food_ids: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)
    max_cook_time_minutes: Annotated[int, Field(ge=1, le=1440)] | None = None
    batch_cooking: BatchCookingPreferences | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class PlanBulkDeleteRequest(BaseModel):
    plan_ids: list[Annotated[int, Field(ge=1)]]

    @field_validator("plan_ids")
    @classmethod
    def validate_plan_ids(cls, value: list[int]) -> list[int]:
        if len(value) == 0:
            raise ValueError("at least one plan is required")
        return value


class PlanBulkDeleteResponse(BaseModel):
    deleted_count: int


class ReplacePlanSlotRequest(BaseModel):
    excluded_recipe_ids: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)
    excluded_food_ids: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)
    use_public_recipes: bool = True
    avoid_current_recipe: bool = True
    max_cook_time_minutes: Annotated[int, Field(ge=1, le=1440)] | None = None


class RegeneratePlanDayRequest(BaseModel):
    excluded_recipe_ids: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)
    excluded_food_ids: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)
    use_public_recipes: bool = True
    max_cook_time_minutes: Annotated[int, Field(ge=1, le=1440)] | None = None


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
    slot_fiber: Decimal
    pinned: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlanSlotIngredientOverrideBaseItem(BaseModel):
    recipe_ingredient_id: Annotated[int, Field(ge=1)]
    food_id: Annotated[int, Field(ge=1)] | None = None
    grams: PositiveDecimal | None = None
    is_excluded: bool = False

    @model_validator(mode="after")
    def validate_payload(self) -> "PlanSlotIngredientOverrideBaseItem":
        if self.is_excluded:
            return self
        if self.food_id is None and self.grams is None:
            raise ValueError("override must include grams or food_id or set is_excluded=true")
        return self


class PlanSlotManualIngredientItem(BaseModel):
    food_id: Annotated[int, Field(ge=1)]
    grams: PositiveDecimal


class PlanSlotIngredientOverridesReplaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_overrides: list[PlanSlotIngredientOverrideBaseItem] = Field(default_factory=list)
    manual_items: list[PlanSlotManualIngredientItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_no_duplicate_base_items(self) -> "PlanSlotIngredientOverridesReplaceRequest":
        recipe_ingredient_ids = [item.recipe_ingredient_id for item in self.base_overrides]
        if len(recipe_ingredient_ids) != len(set(recipe_ingredient_ids)):
            raise ValueError("duplicate recipe_ingredient_id is not allowed")
        return self


class PlanSlotEffectiveIngredientRead(BaseModel):
    recipe_ingredient_id: int | None
    override_id: int | None
    source: str
    food_id: int
    food_name: str
    grams: Decimal
    kcal: Decimal
    protein: Decimal
    fat: Decimal
    carbs: Decimal
    fiber: Decimal


class PlanSlotEffectiveIngredientsResponse(BaseModel):
    slot_id: int
    recipe_id: int
    has_overrides: bool
    excluded_recipe_ingredient_ids: list[int] = Field(default_factory=list)
    items: list[PlanSlotEffectiveIngredientRead]


class NutritionTotalsRead(BaseModel):
    kcal: Decimal
    protein: Decimal
    fat: Decimal
    carbs: Decimal
    fiber: Decimal


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
    target_fiber: int | None
    slots: list[PlanSlotRead]
    days: list[PlanDayRead]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlanAutogenerateResponse(PlanRead):
    pass


NutrientAnalyticsStatus = Literal["low", "ok", "high", "no_target"]


class PlanNutritionTargetRead(BaseModel):
    kcal: int | None
    protein: int | None
    fat: int | None
    carbs: int | None
    fiber: int | None


class NutrientAnalyticsRead(BaseModel):
    total: Decimal
    percent: Decimal | None
    status: NutrientAnalyticsStatus


class PlanDayAnalyticsRead(BaseModel):
    date: date
    kcal: NutrientAnalyticsRead
    protein: NutrientAnalyticsRead
    fat: NutrientAnalyticsRead
    carbs: NutrientAnalyticsRead
    fiber: NutrientAnalyticsRead
    day_score: int


class PlanPeriodAnalyticsRead(BaseModel):
    days_count: int
    average_kcal: Decimal
    average_protein: Decimal
    average_fat: Decimal
    average_carbs: Decimal
    average_fiber: Decimal
    kcal_percent: Decimal | None
    protein_percent: Decimal | None
    fat_percent: Decimal | None
    carbs_percent: Decimal | None
    fiber_percent: Decimal | None
    overall_score: int


class PlanAnalyticsResponse(BaseModel):
    targets: PlanNutritionTargetRead
    period_summary: PlanPeriodAnalyticsRead
    day_analytics: list[PlanDayAnalyticsRead]
    recommendations: list[str]


class PlanListItem(BaseModel):
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
    target_fiber: int | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
