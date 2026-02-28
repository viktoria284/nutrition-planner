from __future__ import annotations

from decimal import Decimal

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


VERIFIED_FOODS_SEED_DATA = [
    {"name": "Яйцо куриное", "brand": None, "kcal": Decimal("155.00"), "protein": Decimal("13.00"), "fat": Decimal("11.00"), "carbs": Decimal("1.10")},
    {"name": "Молоко 2.5%", "brand": "Домик в деревне", "kcal": Decimal("52.00"), "protein": Decimal("2.80"), "fat": Decimal("2.50"), "carbs": Decimal("4.70")},
    {"name": "Кефир 1%", "brand": "Простоквашино", "kcal": Decimal("40.00"), "protein": Decimal("3.00"), "fat": Decimal("1.00"), "carbs": Decimal("4.00")},
    {"name": "Йогурт греческий", "brand": "Danone", "kcal": Decimal("59.00"), "protein": Decimal("10.00"), "fat": Decimal("0.40"), "carbs": Decimal("3.60")},
    {"name": "Творог 5%", "brand": None, "kcal": Decimal("121.00"), "protein": Decimal("17.00"), "fat": Decimal("5.00"), "carbs": Decimal("1.80")},
    {"name": "Сыр твердый", "brand": None, "kcal": Decimal("350.00"), "protein": Decimal("24.00"), "fat": Decimal("27.00"), "carbs": Decimal("1.50")},
    {"name": "Рис отварной", "brand": None, "kcal": Decimal("130.00"), "protein": Decimal("2.40"), "fat": Decimal("0.30"), "carbs": Decimal("28.00")},
    {"name": "Гречка отварная", "brand": None, "kcal": Decimal("110.00"), "protein": Decimal("4.20"), "fat": Decimal("1.10"), "carbs": Decimal("21.30")},
    {"name": "Овсяные хлопья", "brand": "Ясно Солнышко", "kcal": Decimal("366.00"), "protein": Decimal("12.30"), "fat": Decimal("6.10"), "carbs": Decimal("61.80")},
    {"name": "Макароны отварные", "brand": None, "kcal": Decimal("157.00"), "protein": Decimal("5.80"), "fat": Decimal("0.90"), "carbs": Decimal("30.90")},
    {"name": "Хлеб цельнозерновой", "brand": "Хлебный дом", "kcal": Decimal("247.00"), "protein": Decimal("13.00"), "fat": Decimal("4.20"), "carbs": Decimal("41.00")},
    {"name": "Картофель отварной", "brand": None, "kcal": Decimal("87.00"), "protein": Decimal("1.90"), "fat": Decimal("0.10"), "carbs": Decimal("20.10")},
    {"name": "Куриная грудка", "brand": None, "kcal": Decimal("165.00"), "protein": Decimal("31.00"), "fat": Decimal("3.60"), "carbs": Decimal("0.00")},
    {"name": "Индейка филе", "brand": None, "kcal": Decimal("135.00"), "protein": Decimal("29.00"), "fat": Decimal("1.00"), "carbs": Decimal("0.00")},
    {"name": "Говядина постная", "brand": None, "kcal": Decimal("217.00"), "protein": Decimal("26.00"), "fat": Decimal("12.00"), "carbs": Decimal("0.00")},
    {"name": "Лосось", "brand": None, "kcal": Decimal("208.00"), "protein": Decimal("20.00"), "fat": Decimal("13.00"), "carbs": Decimal("0.00")},
    {"name": "Тунец консервированный", "brand": "Магуро", "kcal": Decimal("132.00"), "protein": Decimal("29.00"), "fat": Decimal("1.00"), "carbs": Decimal("0.00")},
    {"name": "Яблоко", "brand": None, "kcal": Decimal("52.00"), "protein": Decimal("0.30"), "fat": Decimal("0.20"), "carbs": Decimal("14.00")},
    {"name": "Банан", "brand": None, "kcal": Decimal("89.00"), "protein": Decimal("1.10"), "fat": Decimal("0.30"), "carbs": Decimal("22.80")},
    {"name": "Апельсин", "brand": None, "kcal": Decimal("47.00"), "protein": Decimal("0.90"), "fat": Decimal("0.10"), "carbs": Decimal("11.80")},
    {"name": "Груша", "brand": None, "kcal": Decimal("57.00"), "protein": Decimal("0.40"), "fat": Decimal("0.10"), "carbs": Decimal("15.00")},
    {"name": "Помидор", "brand": None, "kcal": Decimal("18.00"), "protein": Decimal("0.90"), "fat": Decimal("0.20"), "carbs": Decimal("3.90")},
    {"name": "Огурец", "brand": None, "kcal": Decimal("15.00"), "protein": Decimal("0.70"), "fat": Decimal("0.10"), "carbs": Decimal("3.60")},
    {"name": "Морковь", "brand": None, "kcal": Decimal("41.00"), "protein": Decimal("0.90"), "fat": Decimal("0.20"), "carbs": Decimal("9.60")},
    {"name": "Брокколи", "brand": None, "kcal": Decimal("34.00"), "protein": Decimal("2.80"), "fat": Decimal("0.40"), "carbs": Decimal("6.60")},
    {"name": "Капуста белокочанная", "brand": None, "kcal": Decimal("25.00"), "protein": Decimal("1.30"), "fat": Decimal("0.10"), "carbs": Decimal("5.80")},
    {"name": "Оливковое масло", "brand": "Borges", "kcal": Decimal("884.00"), "protein": Decimal("0.00"), "fat": Decimal("100.00"), "carbs": Decimal("0.00")},
    {"name": "Подсолнечное масло", "brand": "Олейна", "kcal": Decimal("899.00"), "protein": Decimal("0.00"), "fat": Decimal("99.90"), "carbs": Decimal("0.00")},
    {"name": "Арахисовая паста", "brand": "Skippy", "kcal": Decimal("588.00"), "protein": Decimal("25.00"), "fat": Decimal("50.00"), "carbs": Decimal("20.00")},
    {"name": "Фасоль красная вареная", "brand": None, "kcal": Decimal("127.00"), "protein": Decimal("8.70"), "fat": Decimal("0.50"), "carbs": Decimal("22.80")},
]


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


def seed_verified_foods(db: Session) -> int:
    created_count = 0

    for item in VERIFIED_FOODS_SEED_DATA:
        name = item["name"].strip()
        brand = (item.get("brand") or "").strip()

        exists = db.execute(
            select(FoodItem.id).where(
                FoodItem.source == FoodSource.verified,
                func.lower(FoodItem.name) == name.lower(),
                func.lower(func.coalesce(FoodItem.brand, "")) == brand.lower(),
            )
        ).scalar_one_or_none()
        if exists is not None:
            continue

        db.add(
            FoodItem(
                name=name,
                brand=brand or None,
                kcal=item["kcal"],
                protein=item["protein"],
                fat=item["fat"],
                carbs=item["carbs"],
                source=FoodSource.verified,
                status=FoodStatus.approved,
                owner_user_id=None,
            )
        )
        created_count += 1

    db.commit()
    return created_count
