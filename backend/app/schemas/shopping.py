from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

PositiveDecimal = Annotated[Decimal, Field(gt=0)]


class ShoppingListItemRead(BaseModel):
    food_id: int
    name: str
    brand: str | None
    total_grams: Decimal
    checked: bool
    excluded: bool
    adjusted_grams: Decimal | None
    effective_grams: Decimal
    is_manual: Literal[False] = False


class ShoppingManualItemCreate(BaseModel):
    name: str
    grams: PositiveDecimal | None = None
    unit: Annotated[str, Field(max_length=32)] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ShoppingManualItemRead(BaseModel):
    id: int
    name: str
    grams: Decimal | None
    unit: str | None
    checked: bool
    created_at: datetime
    updated_at: datetime
    is_manual: Literal[True] = True

    class Config:
        from_attributes = True


class ShoppingOverrideUpdate(BaseModel):
    checked: bool | None = None
    excluded: bool | None = None
    adjusted_grams: PositiveDecimal | None = None

    @model_validator(mode="after")
    def validate_non_empty_payload(self) -> "ShoppingOverrideUpdate":
        if len(self.model_fields_set) == 0:
            raise ValueError("at least one field must be provided")
        return self


ShoppingListEntryRead = ShoppingListItemRead | ShoppingManualItemRead


class ShoppingListRead(BaseModel):
    items: list[ShoppingListEntryRead]
