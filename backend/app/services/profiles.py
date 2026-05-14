from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.profile import Profile, ProfileExcludedFood, ProfilePreferredFood
from app.schemas.profile import ProfileCreate, ProfileUpdate
from app.services.foods import get_accessible_food_by_id


class ProfileNotFoundError(ValueError):
    pass


class ProfileFoodNotFoundError(ValueError):
    pass


def _profile_query_for_user(*, user_id: int):
    return (
        select(Profile)
        .where(Profile.user_id == user_id)
        .options(
            selectinload(Profile.excluded_food_links),
            selectinload(Profile.preferred_food_links),
        )
    )


def _validate_accessible_food_ids(
    db: Session,
    *,
    user_id: int,
    food_ids: list[int],
) -> list[int]:
    unique_ids = sorted(set(food_ids))
    for food_id in unique_ids:
        food = get_accessible_food_by_id(db, user_id, food_id)
        if food is None:
            raise ProfileFoodNotFoundError(f"Food {food_id} not found")
    return unique_ids


def list_profiles_for_user(db: Session, user_id: int) -> list[Profile]:
    return db.execute(
        _profile_query_for_user(user_id=user_id).order_by(Profile.id.asc())
    ).scalars().all()


def _get_profile_or_404(db: Session, *, user_id: int, profile_id: int) -> Profile:
    profile = db.execute(
        _profile_query_for_user(user_id=user_id).where(Profile.id == profile_id)
    ).scalar_one_or_none()
    if profile is None:
        raise ProfileNotFoundError("Profile not found")
    return profile


def _sync_profile_food_links(
    profile: Profile,
    *,
    excluded_food_ids: list[int],
    preferred_food_ids: list[int],
) -> None:
    profile.excluded_food_links = [
        ProfileExcludedFood(profile_id=profile.id, food_id=food_id)
        for food_id in excluded_food_ids
    ]
    profile.preferred_food_links = [
        ProfilePreferredFood(profile_id=profile.id, food_id=food_id)
        for food_id in preferred_food_ids
    ]


def create_profile_for_user(db: Session, *, user_id: int, payload: ProfileCreate) -> Profile:
    excluded_food_ids = _validate_accessible_food_ids(
        db,
        user_id=user_id,
        food_ids=payload.excluded_food_ids,
    )
    preferred_food_ids = _validate_accessible_food_ids(
        db,
        user_id=user_id,
        food_ids=payload.preferred_food_ids,
    )

    profile = Profile(
        user_id=user_id,
        name=payload.name,
        target_kcal=payload.target_kcal,
        target_protein=payload.target_protein,
        target_fat=payload.target_fat,
        target_carbs=payload.target_carbs,
        target_fiber=payload.target_fiber,
        preferred_categories=payload.preferred_categories,
        max_cook_time_minutes=payload.max_cook_time_minutes,
    )
    db.add(profile)
    db.flush()
    _sync_profile_food_links(
        profile,
        excluded_food_ids=excluded_food_ids,
        preferred_food_ids=preferred_food_ids,
    )

    db.commit()
    db.refresh(profile)
    return _get_profile_or_404(db, user_id=user_id, profile_id=profile.id)


def update_profile_for_user(
    db: Session,
    *,
    user_id: int,
    profile_id: int,
    payload: ProfileUpdate,
) -> Profile:
    profile = _get_profile_or_404(db, user_id=user_id, profile_id=profile_id)
    update_data = payload.model_dump(exclude_unset=True)

    if "excluded_food_ids" in update_data:
        update_data["excluded_food_ids"] = _validate_accessible_food_ids(
            db,
            user_id=user_id,
            food_ids=update_data["excluded_food_ids"] or [],
        )
    if "preferred_food_ids" in update_data:
        update_data["preferred_food_ids"] = _validate_accessible_food_ids(
            db,
            user_id=user_id,
            food_ids=update_data["preferred_food_ids"] or [],
        )

    excluded_food_ids = update_data.pop("excluded_food_ids", None)
    preferred_food_ids = update_data.pop("preferred_food_ids", None)

    if "preferred_categories" in update_data and update_data["preferred_categories"] is None:
        update_data["preferred_categories"] = []

    for field, value in update_data.items():
        setattr(profile, field, value)

    if excluded_food_ids is not None:
        profile.excluded_food_links = [
            ProfileExcludedFood(profile_id=profile.id, food_id=food_id)
            for food_id in excluded_food_ids
        ]
    if preferred_food_ids is not None:
        profile.preferred_food_links = [
            ProfilePreferredFood(profile_id=profile.id, food_id=food_id)
            for food_id in preferred_food_ids
        ]

    db.commit()
    return _get_profile_or_404(db, user_id=user_id, profile_id=profile.id)


def delete_profile_for_user(db: Session, *, user_id: int, profile_id: int) -> None:
    profile = _get_profile_or_404(db, user_id=user_id, profile_id=profile_id)
    db.delete(profile)
    db.commit()
