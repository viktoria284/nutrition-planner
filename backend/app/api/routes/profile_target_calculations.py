from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.profile_target_calculation import (
    ProfileTargetCalculationCreate,
    ProfileTargetCalculationRead,
)
from app.services.profile_target_calculation_service import (
    calculate_and_save_for_user,
    get_latest_calculation_for_user,
)

router = APIRouter(prefix="/profile-target-calculations", tags=["profile_target_calculations"])


@router.post("/calculate", response_model=ProfileTargetCalculationRead)
def calculate_profile_targets(
    payload: ProfileTargetCalculationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return calculate_and_save_for_user(
        db,
        user_id=current_user.id,
        payload=payload,
    )


@router.get("/latest", response_model=ProfileTargetCalculationRead)
def get_latest_profile_targets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    latest = get_latest_calculation_for_user(db, user_id=current_user.id)
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Последний расчёт не найден.",
        )
    return latest
