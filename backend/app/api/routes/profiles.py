from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.profile import Profile
from app.models.user import User
from app.schemas.profile import ProfileCreate, ProfileOut, ProfileUpdate

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=list[ProfileOut])
def list_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.execute(
        select(Profile).where(Profile.user_id == current_user.id).order_by(Profile.id)
    ).scalars().all()


@router.post("", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: ProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = Profile(
        user_id=current_user.id,
        name=payload.name,
        target_kcal=payload.target_kcal,
        target_protein=payload.target_protein,
        target_fat=payload.target_fat,
        target_carbs=payload.target_carbs,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.patch("/{profile_id}", response_model=ProfileOut)
def update_profile(
    profile_id: int,
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.execute(
        select(Profile).where(
            Profile.id == profile_id,
            Profile.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.execute(
        select(Profile).where(
            Profile.id == profile_id,
            Profile.user_id == current_user.id,
        )
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    db.delete(profile)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
