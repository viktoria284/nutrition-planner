from __future__ import annotations

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.enums import FoodSource, FoodStatus
from app.models.foods import FoodItem, FoodReport, FoodServing
from app.schemas.foods import FoodItemCreate, FoodItemUpdate, FoodServingCreate


class FoodPublishConflictError(ValueError):
    pass


class FoodNotEditableError(ValueError):
    pass


class FoodReportConflictError(ValueError):
    pass


class FoodReportNotAllowedError(ValueError):
    pass


class FoodModerationError(ValueError):
    pass


def build_visible_foods_query(
    db: Session,
    user_id: int,
    q: str | None = None,
    *,
    is_admin: bool = False,
) -> Select[tuple[FoodItem]]:
    # db is kept in signature intentionally for consistency with other services.
    _ = db
    query: Select[tuple[FoodItem]] = select(FoodItem)
    if not is_admin:
        visible_condition = or_(
            and_(FoodItem.source == FoodSource.private, FoodItem.owner_user_id == user_id),
            FoodItem.source == FoodSource.verified,
            and_(
                FoodItem.source == FoodSource.community,
                or_(FoodItem.owner_user_id == user_id, FoodItem.status == FoodStatus.approved),
            ),
        )
        query = query.where(visible_condition)

    if q is not None:
        search = q.strip()
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    FoodItem.name.ilike(pattern),
                    func.coalesce(FoodItem.brand, "").ilike(pattern),
                )
            )

    return query


def get_visible_food_by_id(db: Session, user_id: int, food_id: int, *, is_admin: bool = False) -> FoodItem | None:
    query = build_visible_foods_query(db, user_id, is_admin=is_admin).where(FoodItem.id == food_id)
    return db.execute(query).scalar_one_or_none()


def get_accessible_food_by_id(
    db: Session,
    user_id: int,
    food_id: int,
    *,
    is_admin: bool = False,
    include_servings: bool = False,
) -> FoodItem | None:
    query: Select[tuple[FoodItem]] = select(FoodItem).where(FoodItem.id == food_id)

    if include_servings:
        query = query.options(selectinload(FoodItem.servings))

    if not is_admin:
        access_condition = or_(
            and_(FoodItem.source == FoodSource.private, FoodItem.owner_user_id == user_id),
            FoodItem.source == FoodSource.verified,
            and_(
                FoodItem.source == FoodSource.community,
                FoodItem.status.in_([FoodStatus.approved, FoodStatus.pending]),
            ),
            and_(FoodItem.source == FoodSource.community, FoodItem.owner_user_id == user_id),
        )
        query = query.where(access_condition)

    return db.execute(query).scalar_one_or_none()


def get_owned_food_or_none(db: Session, user_id: int, food_id: int) -> FoodItem | None:
    return db.execute(
        select(FoodItem).where(
            FoodItem.id == food_id,
            FoodItem.owner_user_id == user_id,
        )
    ).scalar_one_or_none()


def ensure_editable(food: FoodItem) -> None:
    if food.source != FoodSource.private or food.status != FoodStatus.draft:
        raise FoodNotEditableError("Only private draft foods can be modified")


def create_food(db: Session, user_id: int, data: FoodItemCreate) -> FoodItem:
    food = FoodItem(
        name=data.name,
        brand=data.brand,
        kcal=data.kcal,
        protein=data.protein,
        fat=data.fat,
        carbs=data.carbs,
        owner_user_id=user_id,
        source=FoodSource.private,
        status=FoodStatus.draft,
    )
    db.add(food)
    db.commit()
    db.refresh(food)
    return food


def publish_food(db: Session, user_id: int, food_id: int) -> FoodItem | None:
    food = get_owned_food_or_none(db, user_id, food_id)
    if not food:
        return None

    if food.source in (FoodSource.community, FoodSource.verified):
        raise FoodPublishConflictError("Food is already community or verified and cannot be published")

    food.source = FoodSource.community
    food.status = FoodStatus.approved
    db.commit()
    db.refresh(food)
    return food


def update_food(db: Session, food: FoodItem, payload: FoodItemUpdate) -> FoodItem:
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(food, field, value)

    db.commit()
    db.refresh(food)
    return food


def delete_food(db: Session, food: FoodItem) -> None:
    db.delete(food)
    db.commit()


def list_servings(db: Session, food_id: int) -> list[FoodServing]:
    return db.execute(
        select(FoodServing).where(FoodServing.food_id == food_id).order_by(FoodServing.id)
    ).scalars().all()


def create_serving(db: Session, food: FoodItem, payload: FoodServingCreate) -> FoodServing:
    serving = FoodServing(
        food_id=food.id,
        name=payload.name,
        grams=payload.grams,
    )
    db.add(serving)
    db.commit()
    db.refresh(serving)
    return serving


def get_serving_with_food(db: Session, serving_id: int) -> FoodServing | None:
    return db.execute(
        select(FoodServing)
        .where(FoodServing.id == serving_id)
        .options(selectinload(FoodServing.food))
    ).scalar_one_or_none()


def delete_serving(db: Session, serving: FoodServing) -> None:
    db.delete(serving)
    db.commit()


def report_food(db: Session, reporter_user_id: int, food_id: int, reason: str | None) -> FoodItem | None:
    food = db.execute(
        select(FoodItem).where(FoodItem.id == food_id).with_for_update()
    ).scalar_one_or_none()
    if not food:
        return None

    if food.source != FoodSource.community or food.status != FoodStatus.approved:
        raise FoodReportNotAllowedError("Only community approved foods can be reported")

    if food.owner_user_id == reporter_user_id:
        raise FoodReportNotAllowedError("You cannot report your own food")

    existing_report = db.execute(
        select(FoodReport.id).where(
            FoodReport.food_id == food_id,
            FoodReport.reporter_user_id == reporter_user_id,
        )
    ).scalar_one_or_none()
    if existing_report is not None:
        raise FoodReportConflictError("You have already reported this food")

    db.add(
        FoodReport(
            food_id=food_id,
            reporter_user_id=reporter_user_id,
            reason=reason,
        )
    )

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise FoodReportConflictError("You have already reported this food") from exc

    reports_count = db.execute(
        select(func.count(FoodReport.id)).where(FoodReport.food_id == food_id)
    ).scalar_one()
    food.reports_count = int(reports_count or 0)

    if food.reports_count >= 3 and food.source == FoodSource.community and food.status == FoodStatus.approved:
        food.status = FoodStatus.pending

    db.commit()
    db.refresh(food)
    return food


def moderate_food(db: Session, food_id: int, action: str) -> FoodItem | None:
    food = db.execute(select(FoodItem).where(FoodItem.id == food_id)).scalar_one_or_none()
    if not food:
        return None

    if food.source != FoodSource.community:
        raise FoodModerationError("Only community foods can be moderated")

    if action == "approve":
        food.status = FoodStatus.approved
    elif action == "reject":
        food.status = FoodStatus.rejected
    else:
        raise FoodModerationError("Invalid moderation action")

    db.commit()
    db.refresh(food)
    return food
