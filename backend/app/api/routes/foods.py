from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.enums import FoodSource, UserRole
from app.models.foods import FoodItem
from app.models.user import User
from app.schemas.foods import (
    FoodItemCreate,
    FoodItemRead,
    FoodReportCreate,
    FoodItemUpdate,
    FoodItemWithServingsRead,
    FoodServingCreate,
    FoodServingRead,
)
from app.services.foods import (
    FoodReportConflictError,
    FoodReportNotAllowedError,
    FoodReportSelfError,
    FoodWithdrawConflictError,
    FoodWithdrawForbiddenError,
    FoodPublishConflictError,
    FoodNotEditableError,
    build_visible_foods_query,
    create_food,
    create_serving,
    delete_food,
    ensure_editable,
    get_accessible_food_by_id,
    get_owned_food_or_none,
    list_servings,
    publish_food,
    report_food,
    update_food,
    withdraw_food,
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
    is_admin = current_user.role == UserRole.admin
    query_text = q.strip()
    if len(query_text) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="q must contain at least 2 non-space characters",
        )
    q_lower = query_text.lower()
    prefix_pattern = f"{q_lower}%"

    sort_priority = case(
        (FoodItem.owner_user_id == current_user.id, 0),
        (FoodItem.source == FoodSource.verified, 1),
        else_=2,
    )
    match_rank = case(
        (
            or_(
                func.lower(FoodItem.name).like(prefix_pattern),
                func.lower(func.coalesce(FoodItem.brand, "")).like(prefix_pattern),
            ),
            0,
        ),
        else_=1,
    )

    query = (
        build_visible_foods_query(db, current_user.id, q=query_text, is_admin=is_admin)
        .order_by(sort_priority, match_rank, func.lower(FoodItem.name), FoodItem.id)
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
    is_admin = current_user.role == UserRole.admin
    food = get_accessible_food_by_id(
        db,
        current_user.id,
        food_id,
        is_admin=is_admin,
        include_servings=include_servings,
    )
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


@router.post("/{food_id}/withdraw", response_model=FoodItemRead)
def withdraw_food_item(
    food_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        food = withdraw_food(db, current_user.id, food_id)
    except FoodWithdrawForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except FoodWithdrawConflictError as exc:
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


@router.get("/{food_id}/servings", response_model=list[FoodServingRead])
def list_food_servings(
    food_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    food = get_accessible_food_by_id(
        db,
        current_user.id,
        food_id,
        is_admin=current_user.role == UserRole.admin,
    )
    if not food:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")

    return list_servings(db, food_id)


@router.post("/{food_id}/servings", response_model=FoodServingRead, status_code=status.HTTP_201_CREATED)
def create_food_serving(
    food_id: int,
    payload: FoodServingCreate,
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

    serving = create_serving(db, food, payload)
    return FoodServingRead.model_validate(serving)


@router.post("/{food_id}/reports", response_model=FoodItemRead)
def report_food_item(
    food_id: int,
    payload: FoodReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        food = report_food(db, current_user.id, food_id, payload.reason)
    except (FoodReportSelfError, FoodReportNotAllowedError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FoodReportConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if not food:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")

    return FoodItemRead.model_validate(food)
