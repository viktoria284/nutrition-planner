from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.plan import PlanCreate, PlanListItem, PlanRead, PlanSlotRead, PlanSlotUpdate
from app.services.plans import (
    PlanNotFoundError,
    PlanSlotNotFoundError,
    PlanSlotRecipeNotFoundError,
    build_plan_list_item,
    build_plan_read,
    create_plan,
    delete_plan_for_user,
    get_plan_for_user,
    list_plans_for_user,
    update_plan_slot,
)

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[PlanListItem])
def get_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plans = list_plans_for_user(db, current_user.id)
    return [build_plan_list_item(plan) for plan in plans]


@router.post("", response_model=PlanRead, status_code=status.HTTP_201_CREATED)
def post_plan(
    payload: PlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = create_plan(db, current_user.id, payload)
    return build_plan_read(plan)


@router.get("/{plan_id}", response_model=PlanRead)
def get_plan_by_id(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        plan = get_plan_for_user(db, current_user.id, plan_id)
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found") from exc
    return build_plan_read(plan)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan_by_id(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        delete_plan_for_user(db, current_user.id, plan_id)
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{plan_id}/slots/{slot_id}", response_model=PlanSlotRead)
def patch_plan_slot(
    plan_id: int,
    slot_id: int,
    payload: PlanSlotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        slot = update_plan_slot(db, current_user.id, plan_id, slot_id, payload)
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found") from exc
    except PlanSlotNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan slot not found") from exc
    except PlanSlotRecipeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    return PlanSlotRead.model_validate(slot)
