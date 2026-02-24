from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.models.enums import FoodSource
from app.models.foods import FoodItem
from app.models.user import User
from app.schemas.foods import FoodItemCreate, FoodItemRead, FoodItemUpdate, FoodItemWithServingsRead
from app.services.foods import (
    FoodPublishConflictError,
    FoodNotEditableError,
    build_visible_foods_query,
    create_food,
    delete_food,
    ensure_editable,
    get_owned_food_or_none,
    get_visible_food_by_id,
    publish_food,
    update_food,
)

router = APIRouter(prefix="/foods", tags=["foods"])


@router.post("", response_model=FoodItemRead, status_code=status.HTTP_201_CREATED)
def create_food_item(
    payload: FoodItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    food = create_food(db, current_user.id, payload)
    return FoodItemRead.model_validate(food)


@router.get("/search", response_model=list[FoodItemRead])
def search_foods(
    q: str = Query(...),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query_text = q.strip()
    if len(query_text) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="q must contain at least 2 non-space characters",
        )

    sort_priority = case(
        (FoodItem.owner_user_id == current_user.id, 0),
        (FoodItem.source == FoodSource.verified, 1),
        else_=2,
    )

    query = (
        build_visible_foods_query(db, current_user.id, q=query_text)
        .order_by(sort_priority, func.lower(FoodItem.name), FoodItem.id)
        .limit(limit)
        .offset(offset)
    )
    return db.execute(query).scalars().all()


@router.get("/{food_id}", response_model=FoodItemRead | FoodItemWithServingsRead)
def get_food_by_id(
    food_id: int,
    include_servings: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if include_servings:
        query = (
            build_visible_foods_query(db, current_user.id)
            .where(FoodItem.id == food_id)
            .options(selectinload(FoodItem.servings))
        )
        food = db.execute(query).scalar_one_or_none()
    else:
        food = get_visible_food_by_id(db, current_user.id, food_id)
    if not food:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")

    if include_servings:
        return FoodItemWithServingsRead.model_validate(food)
    return FoodItemRead.model_validate(food)


@router.post("/{food_id}/publish", response_model=FoodItemRead)
def publish_food_item(
    food_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        food = publish_food(db, current_user.id, food_id)
    except FoodPublishConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if not food:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")

    return FoodItemRead.model_validate(food)


@router.patch("/{food_id}", response_model=FoodItemRead)
def patch_food_item(
    food_id: int,
    payload: FoodItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    food = get_owned_food_or_none(db, current_user.id, food_id)
    if not food:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")

    try:
        ensure_editable(food)
    except FoodNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    updated_food = update_food(db, food, payload)
    return FoodItemRead.model_validate(updated_food)


@router.delete("/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_food_item(
    food_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    food = get_owned_food_or_none(db, current_user.id, food_id)
    if not food:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")

    try:
        ensure_editable(food)
    except FoodNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    delete_food(db, food)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
