from __future__ import annotations

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import FoodSource, FoodStatus
from app.models.foods import FoodItem, FoodServing
from app.schemas.foods import FoodItemCreate, FoodItemUpdate, FoodServingCreate


class FoodPublishConflictError(ValueError):
    pass


class FoodNotEditableError(ValueError):
    pass


def build_visible_foods_query(db: Session, user_id: int, q: str | None = None) -> Select[tuple[FoodItem]]:
    # db is kept in signature intentionally for consistency with other services.
    _ = db
    visible_condition = or_(
        and_(FoodItem.source == FoodSource.private, FoodItem.owner_user_id == user_id),
        FoodItem.source == FoodSource.verified,
        and_(
            FoodItem.source == FoodSource.community,
            or_(FoodItem.owner_user_id == user_id, FoodItem.status == FoodStatus.approved),
        ),
    )

    query: Select[tuple[FoodItem]] = select(FoodItem).where(visible_condition)

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


def get_visible_food_by_id(db: Session, user_id: int, food_id: int) -> FoodItem | None:
    query = build_visible_foods_query(db, user_id).where(FoodItem.id == food_id)
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
    food.status = FoodStatus.pending
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
