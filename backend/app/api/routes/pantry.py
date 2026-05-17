from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.pantry import PantryItemCreate, PantryItemRead
from app.services.pantry import PantryFoodNotFoundError, delete_pantry_item, list_pantry_items, upsert_pantry_item

router = APIRouter(prefix="/pantry", tags=["pantry"])


@router.get("", response_model=list[PantryItemRead])
def get_pantry(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_pantry_items(db, current_user.id)


@router.post("", response_model=PantryItemRead, status_code=status.HTTP_201_CREATED)
def post_pantry_item(
    payload: PantryItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return upsert_pantry_item(db, current_user.id, payload)
    except PantryFoodNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found") from exc


@router.delete("/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pantry_food(
    food_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if food_id < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid food_id")
    delete_pantry_item(db, current_user.id, food_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
