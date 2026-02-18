from pydantic import BaseModel


class ProfileCreate(BaseModel):
    name: str
    target_kcal: int
    target_protein: int
    target_fat: int
    target_carbs: int


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
    target_kcal: int
    target_protein: int
    target_fat: int
    target_carbs: int

    class Config:
        from_attributes = True
