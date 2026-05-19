from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

import app.db.base  # noqa: F401

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.author_favorite import AuthorFavorite
from app.models.enums import FoodSource, UserRole
from app.models.foods import FoodItem
from app.models.pantry import UserPantryItem
from app.models.plan import Plan
from app.models.profile import Profile
from app.models.recipe import Recipe, RecipeFavorite, RecipeNote
from app.models.shopping import ShoppingList
from app.models.user import User
from app.schemas.foods import FoodItemCreate
from app.schemas.pantry import PantryItemCreate
from app.schemas.plan import (
    PlanAutogenerateRequest,
    PlanCreate,
    PlanSlotIngredientOverridesReplaceRequest,
    PlanSlotUpdate,
)
from app.schemas.profile import ProfileCreate
from app.schemas.recipes import (
    RecipeCreate,
    RecipeIngredientCreate,
    RecipeStepInput,
    RecipeStepsReplace,
)
from app.schemas.shopping import (
    ShoppingListCreateFromPlanRequest,
    ShoppingListItemUpdate,
    ShoppingListMergeRequest,
    ShoppingManualItemCreate,
)
from app.services.foods import create_food, seed_verified_foods
from app.services.pantry import upsert_pantry_item
from app.services.plan_analytics import get_plan_analytics_for_user
from app.services.plan_autogenerate import autogenerate_plan, get_meal_type_sequence
from app.services.plan_slot_ingredients import replace_slot_ingredient_overrides
from app.services.plans import build_plan_read, create_plan, delete_plan_for_user, get_plan_for_user, update_plan_slot
from app.services.profiles import create_profile_for_user
from app.services.recipes import (
    add_ingredient,
    add_recipe_favorite,
    create_recipe,
    publish_recipe,
    replace_recipe_steps,
)
from app.services.security import hash_password
from app.services.shopping import (
    add_manual_item,
    create_shopping_list_from_plan,
    get_shopping_list,
    merge_shopping_lists,
    update_shopping_list_item,
)

SHOWCASE_EMAIL = "anna.k@example.com"
SHOWCASE_USERNAME = "anna_k"
SHOWCASE_DISPLAY_NAME = "Анна"
SHOWCASE_PASSWORD = "AnnaPass123"

Q = Decimal("0.01")


@dataclass(frozen=True)
class FoodSpec:
    key: str
    aliases: tuple[str, ...]
    fallback_name: str
    fallback_category: str
    kcal: Decimal
    protein: Decimal
    fat: Decimal
    carbs: Decimal
    fiber: Decimal = Decimal("0")


@dataclass(frozen=True)
class RecipeSpec:
    name: str
    meal_types: tuple[str, ...]
    cook_time_minutes: int
    servings_count: int
    description: str
    image_url: str | None
    ingredients: tuple[tuple[str, Decimal], ...]
    steps: tuple[str, ...]


FOODS: tuple[FoodSpec, ...] = (
    FoodSpec("oats", ("овсяные хлопья", "овсянка"), "Овсяные хлопья", "grains_bakery", Decimal("366"), Decimal("12.3"), Decimal("6.1"), Decimal("61.8"), Decimal("8")),
    FoodSpec("banana", ("банан",), "Банан", "fruits", Decimal("89"), Decimal("1.1"), Decimal("0.3"), Decimal("22.8"), Decimal("2.6")),
    FoodSpec("berries", ("ягоды замороженные", "ягоды", "черника", "клубника"), "Ягоды замороженные", "fruits", Decimal("50"), Decimal("0.8"), Decimal("0.3"), Decimal("11.5"), Decimal("4")),
    FoodSpec("egg", ("яйцо куриное", "яйца"), "Яйцо куриное", "eggs", Decimal("155"), Decimal("13"), Decimal("11"), Decimal("1.1"), Decimal("0")),
    FoodSpec("cheese", ("сыр твердый", "сыр"), "Сыр твердый", "dairy", Decimal("350"), Decimal("24"), Decimal("27"), Decimal("1.5"), Decimal("0")),
    FoodSpec("tomato", ("томат", "помидор", "томаты"), "Томат", "vegetables", Decimal("18"), Decimal("0.9"), Decimal("0.2"), Decimal("3.9"), Decimal("1.2")),
    FoodSpec("pepper", ("перец болгарский",), "Перец болгарский", "vegetables", Decimal("31"), Decimal("1"), Decimal("0.3"), Decimal("6"), Decimal("2.1")),
    FoodSpec("spinach", ("шпинат",), "Шпинат", "vegetables", Decimal("23"), Decimal("2.9"), Decimal("0.4"), Decimal("3.6"), Decimal("2.2")),
    FoodSpec("cottage", ("творог 5%", "творог"), "Творог", "dairy", Decimal("121"), Decimal("17"), Decimal("5"), Decimal("1.8"), Decimal("0")),
    FoodSpec("granola", ("гранола",), "Гранола", "grains_bakery", Decimal("430"), Decimal("10"), Decimal("15"), Decimal("64"), Decimal("8")),
    FoodSpec("buckwheat", ("гречка", "гречка отварная"), "Гречка", "grains_bakery", Decimal("110"), Decimal("4.2"), Decimal("1.1"), Decimal("21.3"), Decimal("3.4")),
    FoodSpec("chicken", ("куриная грудка", "курица"), "Куриная грудка", "meat_fish", Decimal("165"), Decimal("31"), Decimal("3.6"), Decimal("0"), Decimal("0")),
    FoodSpec("broccoli", ("брокколи",), "Брокколи", "vegetables", Decimal("34"), Decimal("2.8"), Decimal("0.4"), Decimal("6.6"), Decimal("2.6")),
    FoodSpec("rice", ("рис", "рис отварной"), "Рис", "grains_bakery", Decimal("130"), Decimal("2.4"), Decimal("0.3"), Decimal("28"), Decimal("0.4")),
    FoodSpec("turkey", ("индейка филе", "индейка"), "Индейка", "meat_fish", Decimal("135"), Decimal("29"), Decimal("1"), Decimal("0"), Decimal("0")),
    FoodSpec("pasta", ("макароны", "макароны отварные", "паста"), "Макароны", "grains_bakery", Decimal("157"), Decimal("5.8"), Decimal("0.9"), Decimal("30.9"), Decimal("1.8")),
    FoodSpec("fish", ("треска", "лосось", "рыба"), "Треска", "meat_fish", Decimal("82"), Decimal("18"), Decimal("0.7"), Decimal("0"), Decimal("0")),
    FoodSpec("potato", ("картофель", "картофель отварной"), "Картофель", "vegetables", Decimal("87"), Decimal("1.9"), Decimal("0.1"), Decimal("20.1"), Decimal("2.2")),
    FoodSpec("cucumber", ("огурец",), "Огурец", "vegetables", Decimal("15"), Decimal("0.7"), Decimal("0.1"), Decimal("3.6"), Decimal("0.5")),
    FoodSpec("cabbage", ("капуста белокочанная",), "Капуста белокочанная", "vegetables", Decimal("25"), Decimal("1.3"), Decimal("0.1"), Decimal("5.8"), Decimal("2.5")),
    FoodSpec("yogurt", ("йогурт греческий", "йогурт"), "Йогурт греческий", "dairy", Decimal("59"), Decimal("10"), Decimal("0.4"), Decimal("3.6"), Decimal("0")),
    FoodSpec("apple", ("яблоко",), "Яблоко", "fruits", Decimal("52"), Decimal("0.3"), Decimal("0.2"), Decimal("14"), Decimal("2.4")),
    FoodSpec("walnut", ("орехи грецкие", "орехи"), "Орехи грецкие", "nuts_oils", Decimal("654"), Decimal("15.2"), Decimal("65.2"), Decimal("13.7"), Decimal("6.7")),
    FoodSpec("honey", ("мёд", "мед"), "Мёд", "pantry_spices", Decimal("304"), Decimal("0.3"), Decimal("0"), Decimal("82.4"), Decimal("0")),
    FoodSpec("olive_oil", ("оливковое масло", "масло оливковое"), "Оливковое масло", "nuts_oils", Decimal("884"), Decimal("0"), Decimal("100"), Decimal("0"), Decimal("0")),
    FoodSpec("sunflower_oil", ("подсолнечное масло", "масло растительное"), "Подсолнечное масло", "nuts_oils", Decimal("899"), Decimal("0"), Decimal("99.9"), Decimal("0"), Decimal("0")),
    FoodSpec("paprika", ("паприка",), "Паприка", "pantry_spices", Decimal("282"), Decimal("14.1"), Decimal("12.9"), Decimal("54.7"), Decimal("34.9")),
    FoodSpec("salt", ("соль",), "Соль", "pantry_spices", Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")),
    FoodSpec("black_pepper", ("перец черный молотый", "чёрный перец", "черный перец"), "Перец черный молотый", "pantry_spices", Decimal("251"), Decimal("10.4"), Decimal("3.3"), Decimal("64.8"), Decimal("25.3")),
    FoodSpec("tea", ("чай",), "Чай чёрный", "drinks", Decimal("1"), Decimal("0.1"), Decimal("0"), Decimal("0.2"), Decimal("0")),
)

RECIPES: tuple[RecipeSpec, ...] = (
    RecipeSpec(
        name="Овсянка с бананом и ягодами",
        meal_types=("breakfast", "snack"),
        cook_time_minutes=12,
        servings_count=1,
        description="Быстрый завтрак с медленными углеводами и клетчаткой.",
        image_url="https://picsum.photos/seed/anna-oats/1200/800",
        ingredients=(("oats", Decimal("60")), ("banana", Decimal("100")), ("berries", Decimal("80")), ("honey", Decimal("10"))),
        steps=(
            "Залейте овсяные хлопья горячей водой и варите 5-7 минут до мягкости.",
            "Добавьте нарезанный банан и ягоды, аккуратно перемешайте.",
            "Перед подачей добавьте немного мёда.",
        ),
    ),
    RecipeSpec(
        name="Омлет с овощами и сыром",
        meal_types=("breakfast", "lunch"),
        cook_time_minutes=18,
        servings_count=1,
        description="Сытный омлет с овощами на каждый день.",
        image_url=None,
        ingredients=(("egg", Decimal("180")), ("tomato", Decimal("100")), ("pepper", Decimal("80")), ("cheese", Decimal("30")), ("olive_oil", Decimal("5"))),
        steps=(
            "Взбейте яйца до однородности.",
            "Обжарьте овощи 3-4 минуты на капле масла, залейте яйцами.",
            "Добавьте сыр, накройте крышкой и доведите омлет до готовности.",
        ),
    ),
    RecipeSpec(
        name="Творог с ягодами и гранолой",
        meal_types=("breakfast", "snack"),
        cook_time_minutes=7,
        servings_count=1,
        description="Лёгкий белковый перекус.",
        image_url="https://picsum.photos/seed/anna-curd/1200/800",
        ingredients=(("cottage", Decimal("180")), ("berries", Decimal("80")), ("granola", Decimal("35")), ("honey", Decimal("8"))),
        steps=(
            "Выложите творог в миску и слегка разомните вилкой.",
            "Добавьте ягоды и гранолу.",
            "По желанию добавьте немного мёда и подавайте.",
        ),
    ),
    RecipeSpec(
        name="Гречка с курицей и овощами",
        meal_types=("lunch", "dinner"),
        cook_time_minutes=32,
        servings_count=2,
        description="Универсальное блюдо для обеда и ужина.",
        image_url=None,
        ingredients=(("buckwheat", Decimal("240")), ("chicken", Decimal("260")), ("broccoli", Decimal("180")), ("tomato", Decimal("120")), ("olive_oil", Decimal("8"))),
        steps=(
            "Отварите гречку до готовности.",
            "Курицу нарежьте кусочками и обжарьте до готовности.",
            "Добавьте овощи, прогрейте 5 минут и подавайте с гречкой.",
        ),
    ),
    RecipeSpec(
        name="Рис с индейкой и овощами",
        meal_types=("lunch", "dinner"),
        cook_time_minutes=35,
        servings_count=2,
        description="Сбалансированное блюдо с акцентом на белок.",
        image_url="https://picsum.photos/seed/anna-rice/1200/800",
        ingredients=(("rice", Decimal("260")), ("turkey", Decimal("280")), ("broccoli", Decimal("150")), ("pepper", Decimal("120")), ("olive_oil", Decimal("8"))),
        steps=(
            "Отварите рис до мягкости.",
            "Индейку обжарьте на среднем огне до золотистой корочки.",
            "Добавьте овощи, слегка протушите и соедините с рисом.",
        ),
    ),
    RecipeSpec(
        name="Паста с курицей и томатами",
        meal_types=("lunch", "dinner"),
        cook_time_minutes=28,
        servings_count=2,
        description="Быстрое блюдо для рабочих дней.",
        image_url=None,
        ingredients=(("pasta", Decimal("250")), ("chicken", Decimal("240")), ("tomato", Decimal("180")), ("olive_oil", Decimal("8")), ("paprika", Decimal("2"))),
        steps=(
            "Сварите пасту до состояния al dente.",
            "Обжарьте курицу до готовности, добавьте томаты и паприку.",
            "Смешайте пасту с соусом и подавайте горячей.",
        ),
    ),
    RecipeSpec(
        name="Рыба с картофелем и салатом",
        meal_types=("dinner",),
        cook_time_minutes=34,
        servings_count=2,
        description="Классический ужин с рыбой и овощами.",
        image_url="https://picsum.photos/seed/anna-fish/1200/800",
        ingredients=(("fish", Decimal("320")), ("potato", Decimal("300")), ("cucumber", Decimal("150")), ("cabbage", Decimal("120")), ("olive_oil", Decimal("10"))),
        steps=(
            "Запеките рыбу в духовке до готовности.",
            "Отварите картофель и слегка остудите.",
            "Соберите салат из огурца и капусты, заправьте маслом и подавайте вместе с рыбой.",
        ),
    ),
    RecipeSpec(
        name="Йогурт с яблоком и орехами",
        meal_types=("snack", "breakfast"),
        cook_time_minutes=6,
        servings_count=1,
        description="Перекус на каждый день с белком и полезными жирами.",
        image_url=None,
        ingredients=(("yogurt", Decimal("220")), ("apple", Decimal("130")), ("walnut", Decimal("18")), ("honey", Decimal("6"))),
        steps=(
            "Нарежьте яблоко небольшими кубиками.",
            "Смешайте йогурт с яблоком и орехами.",
            "Добавьте немного мёда перед подачей.",
        ),
    ),
)


def _normalize(value: str) -> str:
    return value.strip().casefold().replace("ё", "е")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Q, rounding=ROUND_HALF_UP)


def _find_matching_food(foods: list[FoodItem], aliases: tuple[str, ...]) -> FoodItem | None:
    normalized_aliases = [_normalize(alias) for alias in aliases]
    for alias in normalized_aliases:
        for food in foods:
            if _normalize(food.name) == alias:
                return food
    for alias in normalized_aliases:
        for food in foods:
            normalized_name = _normalize(food.name)
            if alias in normalized_name or normalized_name in alias:
                return food
    return None


def _collect_visible_foods(db: Session, user_id: int) -> list[FoodItem]:
    return db.execute(
        select(FoodItem).where(
            or_(
                FoodItem.source == FoodSource.verified,
                and_(FoodItem.source == FoodSource.private, FoodItem.owner_user_id == user_id),
            )
        )
    ).scalars().all()


def _ensure_food_map(db: Session, user_id: int) -> dict[str, FoodItem]:
    visible_foods = _collect_visible_foods(db, user_id)
    resolved: dict[str, FoodItem] = {}

    for spec in FOODS:
        found = _find_matching_food(visible_foods, spec.aliases)
        if found is None:
            created = create_food(
                db,
                user_id,
                FoodItemCreate(
                    name=spec.fallback_name,
                    category=spec.fallback_category,
                    kcal=spec.kcal,
                    protein=spec.protein,
                    fat=spec.fat,
                    carbs=spec.carbs,
                    fiber=spec.fiber,
                ),
            )
            visible_foods.append(created)
            found = created
        resolved[spec.key] = found

    return resolved


def _fetch_showcase_users(db: Session) -> list[User]:
    return db.execute(
        select(User).where(
            or_(
                User.email == SHOWCASE_EMAIL,
                User.username == SHOWCASE_USERNAME,
            )
        )
    ).scalars().all()


def _reset_showcase_user_data(db: Session, user_id: int) -> None:
    db.execute(delete(ShoppingList).where(ShoppingList.owner_user_id == user_id))
    db.execute(delete(Plan).where(Plan.owner_user_id == user_id))
    db.execute(delete(Recipe).where(Recipe.owner_user_id == user_id))
    db.execute(delete(RecipeFavorite).where(RecipeFavorite.user_id == user_id))
    db.execute(delete(RecipeNote).where(RecipeNote.user_id == user_id))
    db.execute(delete(UserPantryItem).where(UserPantryItem.user_id == user_id))
    db.execute(delete(Profile).where(Profile.user_id == user_id))
    db.execute(delete(AuthorFavorite).where(or_(AuthorFavorite.user_id == user_id, AuthorFavorite.author_id == user_id)))
    db.commit()


def _ensure_showcase_user(db: Session, *, replace: bool) -> User:
    users = _fetch_showcase_users(db)
    if len(users) > 1:
        raise RuntimeError("Найдено несколько пользователей, совпадающих по email/username для Анны. Очистите дубли.")

    existing = users[0] if users else None
    if existing is not None and replace:
        _reset_showcase_user_data(db, existing.id)
        db.execute(delete(User).where(User.id == existing.id))
        db.commit()
        existing = None

    if existing is None:
        user = User(
            email=SHOWCASE_EMAIL,
            username=SHOWCASE_USERNAME,
            display_name=SHOWCASE_DISPLAY_NAME,
            hashed_password=hash_password(SHOWCASE_PASSWORD),
            is_active=True,
            role=UserRole.user,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    _reset_showcase_user_data(db, existing.id)
    existing.email = SHOWCASE_EMAIL
    existing.username = SHOWCASE_USERNAME
    existing.display_name = SHOWCASE_DISPLAY_NAME
    existing.hashed_password = hash_password(SHOWCASE_PASSWORD)
    existing.is_active = True
    existing.role = UserRole.user
    db.commit()
    db.refresh(existing)
    return existing


def _create_profiles(db: Session, user_id: int, food_map: dict[str, FoodItem]) -> dict[str, Profile]:
    profiles: dict[str, Profile] = {}

    maintain = create_profile_for_user(
        db,
        user_id=user_id,
        payload=ProfileCreate(
            name="Поддержание формы",
            target_kcal=2220,
            target_protein=120,
            target_fat=60,
            target_carbs=300,
            target_fiber=28,
            max_cook_time_minutes=35,
            excluded_terms=["майонез", "колбаса", "фритюр", "сливочный соус"],
            excluded_categories=["sweets", "pantry_spices", "other"],
            preferred_categories=["grains_bakery", "vegetables", "meat_fish", "dairy"],
            preferred_food_ids=[
                food_map["oats"].id,
                food_map["buckwheat"].id,
                food_map["rice"].id,
                food_map["chicken"].id,
                food_map["turkey"].id,
                food_map["cottage"].id,
                food_map["yogurt"].id,
                food_map["broccoli"].id,
                food_map["apple"].id,
            ],
        ),
    )
    profiles["maintain"] = maintain

    profiles["mass"] = create_profile_for_user(
        db,
        user_id=user_id,
        payload=ProfileCreate(
            name="Набор массы",
            target_kcal=3200,
            target_protein=170,
            target_fat=95,
            target_carbs=430,
            target_fiber=35,
            max_cook_time_minutes=45,
        ),
    )

    profiles["light"] = create_profile_for_user(
        db,
        user_id=user_id,
        payload=ProfileCreate(
            name="Лёгкий рацион",
            target_kcal=1800,
            target_protein=105,
            target_fat=55,
            target_carbs=200,
            target_fiber=25,
            max_cook_time_minutes=30,
        ),
    )
    return profiles


def _seed_pantry(db: Session, user_id: int, food_map: dict[str, FoodItem]) -> None:
    pantry_keys = (
        "salt",
        "black_pepper",
        "paprika",
        "olive_oil",
        "sunflower_oil",
        "oats",
        "rice",
        "buckwheat",
        "pasta",
        "egg",
        "tea",
        "honey",
    )
    for key in pantry_keys:
        upsert_pantry_item(db, user_id, PantryItemCreate(food_id=food_map[key].id))


def _seed_recipes(db: Session, user_id: int, food_map: dict[str, FoodItem]) -> dict[str, Recipe]:
    created: dict[str, Recipe] = {}
    for spec in RECIPES:
        recipe = create_recipe(
            db,
            user_id,
            RecipeCreate(
                name=spec.name,
                description=spec.description,
                instructions="Подробные шаги приготовления указаны ниже.",
                image_url=spec.image_url,
                servings_count=spec.servings_count,
                meal_types=list(spec.meal_types),
                cook_time_minutes=spec.cook_time_minutes,
            ),
        )
        for food_key, grams in spec.ingredients:
            add_ingredient(
                db,
                user_id,
                recipe.id,
                RecipeIngredientCreate(food_id=food_map[food_key].id, grams=grams),
            )
        replace_recipe_steps(
            db,
            user_id,
            recipe.id,
            RecipeStepsReplace(
                steps=[RecipeStepInput(position=index + 1, text=step_text) for index, step_text in enumerate(spec.steps)]
            ),
        )
        created[spec.name] = recipe
    return created


def _publish_public_recipes(db: Session, user_id: int, recipes_by_name: dict[str, Recipe]) -> None:
    for recipe_name in ("Омлет с овощами и сыром", "Рыба с картофелем и салатом"):
        recipe = recipes_by_name[recipe_name]
        publish_recipe(db, user_id, recipe.id)


def _mark_recipe_favorites(db: Session, user_id: int, recipes_by_name: dict[str, Recipe]) -> None:
    for recipe_name in (
        "Овсянка с бананом и ягодами",
        "Омлет с овощами и сыром",
        "Творог с ягодами и гранолой",
        "Гречка с курицей и овощами",
        "Рис с индейкой и овощами",
        "Йогурт с яблоком и орехами",
    ):
        add_recipe_favorite(db, user_id=user_id, recipe_id=recipes_by_name[recipe_name].id)


def _sorted_slots(plan: Plan):
    return sorted(plan.slots, key=lambda slot: (slot.day_date, slot.slot_index, slot.id))


def _assign_plan_slots(
    db: Session,
    user_id: int,
    plan_id: int,
    recipes_by_name: dict[str, Recipe],
) -> Plan:
    plan = get_plan_for_user(db, user_id, plan_id)
    meal_sequence = get_meal_type_sequence(plan.meals_per_day)

    meal_pool = {
        "breakfast": [
            recipes_by_name["Овсянка с бананом и ягодами"].id,
            recipes_by_name["Омлет с овощами и сыром"].id,
            recipes_by_name["Творог с ягодами и гранолой"].id,
            recipes_by_name["Йогурт с яблоком и орехами"].id,
        ],
        "lunch": [
            recipes_by_name["Гречка с курицей и овощами"].id,
            recipes_by_name["Рис с индейкой и овощами"].id,
            recipes_by_name["Паста с курицей и томатами"].id,
        ],
        "dinner": [
            recipes_by_name["Рыба с картофелем и салатом"].id,
            recipes_by_name["Гречка с курицей и овощами"].id,
            recipes_by_name["Рис с индейкой и овощами"].id,
            recipes_by_name["Паста с курицей и томатами"].id,
        ],
        "snack": [
            recipes_by_name["Йогурт с яблоком и орехами"].id,
            recipes_by_name["Творог с ягодами и гранолой"].id,
            recipes_by_name["Овсянка с бананом и ягодами"].id,
        ],
    }
    meal_counters = {key: 0 for key in meal_pool}

    for slot in _sorted_slots(plan):
        day_offset = (slot.day_date - plan.start_date).days
        meal_type = meal_sequence[slot.slot_index]
        candidates = meal_pool.get(meal_type)
        if not candidates:
            continue
        idx = (meal_counters[meal_type] + day_offset) % len(candidates)
        meal_counters[meal_type] += 1
        update_plan_slot(
            db,
            user_id,
            plan.id,
            slot.id,
            PlanSlotUpdate(recipe_id=candidates[idx], servings_multiplier=Decimal("1")),
        )

    return get_plan_for_user(db, user_id, plan.id)


def _build_showcase_plans(
    db: Session,
    user_id: int,
    *,
    profiles: dict[str, Profile],
    recipes_by_name: dict[str, Recipe],
    food_map: dict[str, FoodItem],
) -> dict[str, Plan]:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    weekend = monday + timedelta(days=5)
    next_monday = monday + timedelta(days=7)

    work_plan = create_plan(
        db,
        user_id,
        PlanCreate(
            title="Рабочая неделя",
            start_date=monday,
            days_count=5,
            meals_per_day=4,
            profile_id=profiles["maintain"].id,
        ),
    )
    work_plan = _assign_plan_slots(db, user_id, work_plan.id, recipes_by_name)

    work_slots = _sorted_slots(work_plan)
    if len(work_slots) >= 3:
        update_plan_slot(db, user_id, work_plan.id, work_slots[0].id, PlanSlotUpdate(pinned=True))
        update_plan_slot(db, user_id, work_plan.id, work_slots[1].id, PlanSlotUpdate(servings_multiplier=Decimal("1.30")))

        slot_for_override = get_plan_for_user(db, user_id, work_plan.id).slots[2]
        hydrated_plan = get_plan_for_user(db, user_id, work_plan.id)
        hydrated_slot = next(slot for slot in hydrated_plan.slots if slot.id == slot_for_override.id)
        if hydrated_slot.recipe is not None and hydrated_slot.recipe.ingredients:
            base_ingredient = sorted(hydrated_slot.recipe.ingredients, key=lambda item: item.id)[0]
            override_grams = _quantize(base_ingredient.grams * Decimal("0.60"))
            if override_grams <= 0:
                override_grams = Decimal("5.00")
            replace_slot_ingredient_overrides(
                db,
                user_id=user_id,
                plan_id=work_plan.id,
                slot_id=hydrated_slot.id,
                payload=PlanSlotIngredientOverridesReplaceRequest(
                    base_overrides=[
                        {
                            "recipe_ingredient_id": base_ingredient.id,
                            "food_id": None,
                            "grams": override_grams,
                            "is_excluded": False,
                        }
                    ],
                    manual_items=[
                        {
                            "food_id": food_map["paprika"].id,
                            "grams": Decimal("2.00"),
                        }
                    ],
                ),
            )

    weekend_plan = create_plan(
        db,
        user_id,
        PlanCreate(
            title="Выходные",
            start_date=weekend,
            days_count=2,
            meals_per_day=3,
            profile_id=profiles["maintain"].id,
        ),
    )
    weekend_plan = _assign_plan_slots(db, user_id, weekend_plan.id, recipes_by_name)

    next_week_plan = autogenerate_plan(
        db,
        user_id=user_id,
        payload=PlanAutogenerateRequest(
            title="Следующая неделя",
            start_date=next_monday,
            days_count=7,
            meals_per_day=5,
            profile_id=profiles["mass"].id,
            use_public_recipes=True,
            favorite_recipes_mode="prefer",
        ),
    )

    # Service-level sanity check for autoplanning with profile "Поддержание формы" in 5x4 mode.
    smoke_plan = autogenerate_plan(
        db,
        user_id=user_id,
        payload=PlanAutogenerateRequest(
            title="Автоплан на 5 дней",
            start_date=next_monday + timedelta(days=8),
            days_count=5,
            meals_per_day=4,
            profile_id=profiles["maintain"].id,
            use_public_recipes=True,
            favorite_recipes_mode="prefer",
        ),
    )
    delete_plan_for_user(db, user_id, smoke_plan.id)

    refreshed_work = get_plan_for_user(db, user_id, work_plan.id)
    plan_read = build_plan_read(refreshed_work)
    if not any(day.totals.kcal > 0 for day in plan_read.days):
        raise RuntimeError("Не удалось заполнить план 'Рабочая неделя': суточные итоги равны нулю.")
    _ = get_plan_analytics_for_user(db, user_id=user_id, plan_id=work_plan.id)

    return {
        "work": refreshed_work,
        "weekend": get_plan_for_user(db, user_id, weekend_plan.id),
        "next": get_plan_for_user(db, user_id, next_week_plan.id),
    }


def _seed_shopping_lists(db: Session, user_id: int, plans: dict[str, Plan]) -> dict[str, int]:
    week = create_shopping_list_from_plan(
        db,
        user_id,
        ShoppingListCreateFromPlanRequest(
            plan_id=plans["work"].id,
            title="Покупки на рабочую неделю",
        ),
    )
    weekend = create_shopping_list_from_plan(
        db,
        user_id,
        ShoppingListCreateFromPlanRequest(
            plan_id=plans["weekend"].id,
            title="Покупки на выходные",
        ),
    )
    merged = merge_shopping_lists(
        db,
        user_id,
        ShoppingListMergeRequest(
            shopping_list_ids=[week.id, weekend.id],
            title="Общий список покупок",
        ),
    )

    add_manual_item(
        db,
        user_id,
        week.id,
        ShoppingManualItemCreate(name="Лимон", category="fruits", unit="шт"),
    )
    add_manual_item(
        db,
        user_id,
        week.id,
        ShoppingManualItemCreate(name="Минеральная вода", category="drinks", unit="бут."),
    )

    week_filled = get_shopping_list(db, user_id, week.id)
    checked_count = 0
    for item in week_filled.items:
        if item.item_type == "computed" and checked_count < 3:
            update_shopping_list_item(
                db,
                user_id,
                week.id,
                item.id,
                ShoppingListItemUpdate(checked=True),
            )
            checked_count += 1

    week_refreshed = get_shopping_list(db, user_id, week.id)
    quantity_item = next((item for item in week_refreshed.items if item.item_type == "computed" and item.planned_grams), None)
    if quantity_item and quantity_item.planned_grams:
        update_shopping_list_item(
            db,
            user_id,
            week.id,
            quantity_item.id,
            ShoppingListItemUpdate(adjusted_grams=_quantize(quantity_item.planned_grams * Decimal("1.15"))),
        )

    return {"week": week.id, "weekend": weekend.id, "merged": merged.id}


def seed_showcase_data(*, replace: bool) -> dict[str, object]:
    db = SessionLocal()
    try:
        created_verified = seed_verified_foods(db, replace_existing_values=False)
        user = _ensure_showcase_user(db, replace=replace)
        food_map = _ensure_food_map(db, user.id)
        profiles = _create_profiles(db, user.id, food_map)
        _seed_pantry(db, user.id, food_map)
        recipes_by_name = _seed_recipes(db, user.id, food_map)
        _publish_public_recipes(db, user.id, recipes_by_name)
        _mark_recipe_favorites(db, user.id, recipes_by_name)
        plans = _build_showcase_plans(
            db,
            user.id,
            profiles=profiles,
            recipes_by_name=recipes_by_name,
            food_map=food_map,
        )
        shopping_ids = _seed_shopping_lists(db, user.id, plans)

        return {
            "user_id": user.id,
            "verified_foods_created": created_verified,
            "profiles": {key: profile.id for key, profile in profiles.items()},
            "recipes_count": len(recipes_by_name),
            "plans": {key: plan.id for key, plan in plans.items()},
            "shopping_lists": shopping_ids,
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed realistic showcase data for pre-defense recordings")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace existing showcase user data before seeding",
    )
    args = parser.parse_args()

    result = seed_showcase_data(replace=args.replace)
    print(
        "Showcase seed completed. "
        f"user_id={result['user_id']}, "
        f"verified_foods_created={result['verified_foods_created']}, "
        f"profiles={result['profiles']}, "
        f"recipes_count={result['recipes_count']}, "
        f"plans={result['plans']}, "
        f"shopping_lists={result['shopping_lists']}"
    )


if __name__ == "__main__":
    main()
