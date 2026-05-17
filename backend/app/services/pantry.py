from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.foods import FoodItem
from app.models.pantry import UserPantryItem
from app.schemas.pantry import PantryItemCreate, PantryItemRead
from app.services.foods import get_visible_food_by_id


class PantryFoodNotFoundError(ValueError):
    pass


def list_pantry_items(db: Session, user_id: int) -> list[PantryItemRead]:
    rows = db.execute(
        select(UserPantryItem, FoodItem)
        .join(FoodItem, FoodItem.id == UserPantryItem.food_id)
        .where(UserPantryItem.user_id == user_id)
        .order_by(FoodItem.name.asc(), FoodItem.id.asc())
    ).all()

    return [
        PantryItemRead.model_validate(
            {
                "id": pantry.id,
                "user_id": pantry.user_id,
                "food_id": pantry.food_id,
                "note": pantry.note,
                "created_at": pantry.created_at,
                "food": {
                    "id": food.id,
                    "name": food.name,
                    "brand": food.brand,
                    "category": food.category,
                },
            }
        )
        for pantry, food in rows
    ]


def upsert_pantry_item(db: Session, user_id: int, payload: PantryItemCreate) -> PantryItemRead:
    visible_food = get_visible_food_by_id(db, user_id, payload.food_id)
    if visible_food is None:
        raise PantryFoodNotFoundError("Food not found")

    existing = db.execute(
        select(UserPantryItem).where(
            UserPantryItem.user_id == user_id,
            UserPantryItem.food_id == payload.food_id,
        )
    ).scalar_one_or_none()

    if existing is None:
        pantry_item = UserPantryItem(
            user_id=user_id,
            food_id=payload.food_id,
            note=payload.note,
        )
        db.add(pantry_item)
        db.commit()
        db.refresh(pantry_item)
    else:
        pantry_item = existing
        if payload.note is not None and pantry_item.note != payload.note:
            pantry_item.note = payload.note
            db.commit()
            db.refresh(pantry_item)

    return PantryItemRead.model_validate(
        {
            "id": pantry_item.id,
            "user_id": pantry_item.user_id,
            "food_id": pantry_item.food_id,
            "note": pantry_item.note,
            "created_at": pantry_item.created_at,
            "food": {
                "id": visible_food.id,
                "name": visible_food.name,
                "brand": visible_food.brand,
                "category": visible_food.category,
            },
        }
    )


def delete_pantry_item(db: Session, user_id: int, food_id: int) -> None:
    db.execute(
        UserPantryItem.__table__.delete().where(
            UserPantryItem.user_id == user_id,
            UserPantryItem.food_id == food_id,
        )
    )
    db.commit()


def list_pantry_food_ids(db: Session, user_id: int) -> set[int]:
    rows = db.execute(select(UserPantryItem.food_id).where(UserPantryItem.user_id == user_id)).scalars().all()
    return {int(food_id) for food_id in rows}
