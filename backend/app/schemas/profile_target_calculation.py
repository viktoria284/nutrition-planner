from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field
from pydantic import model_validator

Age = Annotated[int, Field(ge=18, le=100)]
HeightCm = Annotated[float, Field(ge=100, le=250)]
WeightKg = Annotated[float, Field(ge=30, le=300)]

Sex = Literal["male", "female"]
ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very_active"]
Goal = Literal["maintain", "lose", "gain"]
Formula = Literal["mifflin_st_jeor", "revised_harris_benedict", "who_fao_unu"]
MacroPreset = Literal["balanced", "higher_protein", "higher_carb"]
SpecialCondition = Literal["none", "pregnant", "breastfeeding", "medical_special_diet"]
LactationPeriod = Literal["first_6_months", "after_6_months", "unknown"]


class ProfileTargetCalculationCreate(BaseModel):
    sex: Sex
    age: Age
    height_cm: HeightCm
    weight_kg: WeightKg
    activity_level: ActivityLevel
    goal: Goal
    formula: Formula = "mifflin_st_jeor"
    macro_preset: MacroPreset
    special_condition: SpecialCondition = "none"
    lactation_period: LactationPeriod | None = None

    @model_validator(mode="after")
    def validate_special_condition(self) -> "ProfileTargetCalculationCreate":
        if self.special_condition == "breastfeeding":
            if self.lactation_period is None:
                self.lactation_period = "unknown"
            return self
        self.lactation_period = None
        return self


class ProfileTargetCalculationRead(BaseModel):
    id: int
    user_id: int
    sex: Sex
    age: Age
    height_cm: float
    weight_kg: float
    activity_level: ActivityLevel
    goal: Goal
    formula: Formula
    macro_preset: MacroPreset
    special_condition: SpecialCondition
    lactation_period: LactationPeriod | None
    bmr: int
    tdee: int
    target_kcal: int
    target_protein: float
    target_fat: float
    target_carbs: float
    target_fiber: float
    warning_message: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProfileTargetCalculationApplyResult(BaseModel):
    detail: str = "Последний расчёт успешно применён к профилю."
