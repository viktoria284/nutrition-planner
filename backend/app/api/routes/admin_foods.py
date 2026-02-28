from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.permissions import require_admin
from app.models.user import User
from app.schemas.foods import FoodItemRead
from app.services.foods import FoodModerationError, moderate_food

router = APIRouter(prefix="/admin/foods", tags=["admin-foods"])


@router.put("/{food_id}/moderate", response_model=FoodItemRead)
def moderate_food_item(
    food_id: int,
    action: Literal["approve", "reject"] = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _ = current_user
    try:
        food = moderate_food(db, food_id, action)
    except FoodModerationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if not food:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")
    return FoodItemRead.model_validate(food)
