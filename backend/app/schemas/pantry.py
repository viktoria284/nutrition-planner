from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class PantryFoodRead(BaseModel):
    id: int
    name: str
    brand: str | None
    category: str

    class Config:
        from_attributes = True


class PantryItemCreate(BaseModel):
    food_id: Annotated[int, Field(ge=1)]
    note: Annotated[str, Field(max_length=255)] | None = None

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class PantryItemRead(BaseModel):
    id: int
    user_id: int
    food_id: int
    note: str | None
    created_at: datetime
    food: PantryFoodRead
