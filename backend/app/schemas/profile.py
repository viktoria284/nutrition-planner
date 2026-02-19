from typing import Annotated

from pydantic import BaseModel, Field

TargetKcal = Annotated[int, Field(ge=0, le=20000)]
TargetGrams = Annotated[int, Field(ge=0, le=2000)]


class ProfileCreate(BaseModel):
    name: str
    target_kcal: TargetKcal | None = None
    target_protein: TargetGrams | None = None
    target_fat: TargetGrams | None = None
    target_carbs: TargetGrams | None = None


class ProfileUpdate(BaseModel):
    name: str | None = None
    target_kcal: TargetKcal | None = None
    target_protein: TargetGrams | None = None
    target_fat: TargetGrams | None = None
    target_carbs: TargetGrams | None = None


class ProfileOut(BaseModel):
    id: int
    user_id: int
    name: str
    target_kcal: int | None
    target_protein: int | None
    target_fat: int | None
    target_carbs: int | None

    class Config:
        from_attributes = True
