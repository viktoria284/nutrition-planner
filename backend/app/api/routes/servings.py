from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.foods import (
    FoodNotEditableError,
    delete_serving,
    ensure_editable,
    get_serving_with_food,
)

router = APIRouter(prefix="/servings", tags=["servings"])


@router.delete("/{serving_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_food_serving(
    serving_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    serving = get_serving_with_food(db, serving_id)
    if not serving or not serving.food or serving.food.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serving not found")

    try:
        ensure_editable(serving.food)
    except FoodNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    delete_serving(db, serving)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
