from pydantic import BaseModel


class ProfileCreate(BaseModel):
    name: str
    target_kcal: int | None = None
    target_protein: int | None = None
    target_fat: int | None = None
    target_carbs: int | None = None


class ProfileUpdate(BaseModel):
    name: str | None = None
    target_kcal: int | None = None
    target_protein: int | None = None
    target_fat: int | None = None
    target_carbs: int | None = None


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
