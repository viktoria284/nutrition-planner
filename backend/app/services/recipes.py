from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.enums import FoodSource, FoodStatus
from app.models.recipe import Recipe, RecipeIngredient, RecipeReport
from app.schemas.recipes import (
    RecipeCreate,
    RecipeIngredientCreate,
    RecipeIngredientUpdate,
    RecipeRead,
    RecipeReportCreate,
    RecipeUpdate,
)
from app.services.foods import get_accessible_food_by_id

NUTRIENT_QUANT = Decimal("0.01")
HUNDRED_GRAMS = Decimal("100")


class RecipeNotFoundError(ValueError):
    pass


class RecipeIngredientNotFoundError(ValueError):
    pass


class RecipeIngredientFoodNotFoundError(ValueError):
    pass


class RecipePublishConflictError(ValueError):
    pass


class RecipeNotEditableError(ValueError):
    pass


class RecipeReportConflictError(ValueError):
    pass


class RecipeReportNotAllowedError(ValueError):
    pass


class RecipeReportSelfError(ValueError):
    pass


class RecipeWithdrawForbiddenError(ValueError):
    pass


class RecipeWithdrawConflictError(ValueError):
    pass


def _quantize_nutrient(value: Decimal) -> Decimal:
    return value.quantize(NUTRIENT_QUANT, rounding=ROUND_HALF_UP)


def ensure_recipe_editable(recipe: Recipe) -> None:
    if recipe.source != FoodSource.private or recipe.status != FoodStatus.draft:
        raise RecipeNotEditableError("Only private draft recipes can be modified")


def create_recipe(db: Session, owner_id: int, data: RecipeCreate) -> Recipe:
    recipe = Recipe(
        owner_user_id=owner_id,
        name=data.name,
        description=data.description,
        servings_count=data.servings_count,
        meal_types=data.meal_types,
        source=FoodSource.private,
        status=FoodStatus.draft,
        is_listed=True,
        reports_count=0,
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


def list_my_recipes(
    db: Session,
    owner_id: int,
    limit: int = 50,
    offset: int = 0,
    *,
    include_ingredients: bool = False,
) -> list[Recipe]:
    query = (
        select(Recipe)
        .where(Recipe.owner_user_id == owner_id)
        .order_by(Recipe.updated_at.desc(), Recipe.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if include_ingredients:
        query = query.options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.food)
        )
    return db.execute(query).scalars().all()


def get_my_recipe_or_404(
    db: Session,
    owner_id: int,
    recipe_id: int,
    *,
    include_ingredients: bool = False,
) -> Recipe:
    query = select(Recipe).where(
        Recipe.id == recipe_id,
        Recipe.owner_user_id == owner_id,
    )
    if include_ingredients:
        query = query.options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.food)
        )
    recipe = db.execute(query).scalar_one_or_none()
    if not recipe:
        raise RecipeNotFoundError("Recipe not found")
    return recipe


def get_owned_recipe_or_none(
    db: Session,
    owner_id: int,
    recipe_id: int,
    *,
    include_ingredients: bool = False,
) -> Recipe | None:
    query = select(Recipe).where(
        Recipe.id == recipe_id,
        Recipe.owner_user_id == owner_id,
    )
    if include_ingredients:
        query = query.options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.food)
        )
    return db.execute(query).scalar_one_or_none()


def get_accessible_recipe_by_id(
    db: Session,
    user_id: int,
    recipe_id: int,
    *,
    include_ingredients: bool = False,
) -> Recipe | None:
    query = select(Recipe).where(Recipe.id == recipe_id)
    if include_ingredients:
        query = query.options(
            selectinload(Recipe.ingredients).selectinload(RecipeIngredient.food)
        )

    query = query.where(
        or_(
            Recipe.owner_user_id == user_id,
            and_(
                Recipe.source == FoodSource.community,
                Recipe.status == FoodStatus.approved,
                Recipe.is_listed.is_(True),
            ),
        )
    )
    return db.execute(query).scalar_one_or_none()


def update_my_recipe(db: Session, owner_id: int, recipe_id: int, data: RecipeUpdate) -> Recipe:
    recipe = get_my_recipe_or_404(db, owner_id, recipe_id)
    ensure_recipe_editable(recipe)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(recipe, field, value)

    db.commit()
    db.refresh(recipe)
    return recipe


def delete_my_recipe(db: Session, owner_id: int, recipe_id: int) -> None:
    recipe = get_my_recipe_or_404(db, owner_id, recipe_id)
    ensure_recipe_editable(recipe)
    db.delete(recipe)
    db.commit()


def _get_recipe_ingredient_or_404(db: Session, recipe_id: int, ingredient_id: int) -> RecipeIngredient:
    ingredient = db.execute(
        select(RecipeIngredient).where(
            RecipeIngredient.id == ingredient_id,
            RecipeIngredient.recipe_id == recipe_id,
        )
    ).scalar_one_or_none()
    if not ingredient:
        raise RecipeIngredientNotFoundError("Ingredient not found")
    return ingredient


def add_ingredient(
    db: Session,
    owner_id: int,
    recipe_id: int,
    data: RecipeIngredientCreate,
) -> RecipeIngredient:
    recipe = get_my_recipe_or_404(db, owner_id, recipe_id)
    ensure_recipe_editable(recipe)
    food = get_accessible_food_by_id(db, owner_id, data.food_id)
    if not food:
        raise RecipeIngredientFoodNotFoundError("Food not found")

    ingredient = RecipeIngredient(
        recipe_id=recipe.id,
        food_id=data.food_id,
        grams=data.grams,
    )
    db.add(ingredient)
    db.commit()
    db.refresh(ingredient)
    return ingredient


def update_ingredient(
    db: Session,
    owner_id: int,
    recipe_id: int,
    ingredient_id: int,
    data: RecipeIngredientUpdate,
) -> RecipeIngredient:
    recipe = get_my_recipe_or_404(db, owner_id, recipe_id)
    ensure_recipe_editable(recipe)
    ingredient = _get_recipe_ingredient_or_404(db, recipe.id, ingredient_id)

    update_data = data.model_dump(exclude_unset=True)
    if "food_id" in update_data:
        food = get_accessible_food_by_id(db, owner_id, update_data["food_id"])
        if not food:
            raise RecipeIngredientFoodNotFoundError("Food not found")

    for field, value in update_data.items():
        setattr(ingredient, field, value)

    db.commit()
    db.refresh(ingredient)
    return ingredient


def delete_ingredient(db: Session, owner_id: int, recipe_id: int, ingredient_id: int) -> None:
    recipe = get_my_recipe_or_404(db, owner_id, recipe_id)
    ensure_recipe_editable(recipe)
    ingredient = _get_recipe_ingredient_or_404(db, recipe.id, ingredient_id)
    db.delete(ingredient)
    db.commit()


def publish_recipe(db: Session, owner_id: int, recipe_id: int) -> Recipe | None:
    recipe = get_owned_recipe_or_none(db, owner_id, recipe_id)
    if not recipe:
        return None

    if recipe.source != FoodSource.private or recipe.status != FoodStatus.draft:
        raise RecipePublishConflictError("Recipe is already published or cannot be published")

    recipe.source = FoodSource.community
    recipe.status = FoodStatus.approved
    recipe.is_listed = True
    db.commit()
    db.refresh(recipe)
    return recipe


def withdraw_recipe(db: Session, owner_id: int, recipe_id: int) -> Recipe | None:
    recipe = db.execute(select(Recipe).where(Recipe.id == recipe_id)).scalar_one_or_none()
    if not recipe:
        return None

    if recipe.owner_user_id != owner_id:
        raise RecipeWithdrawForbiddenError("Only owner can withdraw this recipe")

    if recipe.source != FoodSource.community or recipe.status != FoodStatus.approved:
        raise RecipeWithdrawConflictError("Only approved community recipes can be withdrawn")

    if not recipe.is_listed:
        raise RecipeWithdrawConflictError("Recipe is already withdrawn")

    recipe.is_listed = False
    db.commit()
    db.refresh(recipe)
    return recipe


def report_recipe(
    db: Session,
    reporter_user_id: int,
    recipe_id: int,
    payload: RecipeReportCreate,
) -> Recipe | None:
    recipe = db.execute(
        select(Recipe).where(Recipe.id == recipe_id).with_for_update()
    ).scalar_one_or_none()
    if not recipe:
        return None

    if recipe.owner_user_id == reporter_user_id:
        raise RecipeReportSelfError("You cannot report your own recipe")

    if (
        recipe.source != FoodSource.community
        or recipe.status != FoodStatus.approved
        or not recipe.is_listed
    ):
        return None

    db.add(
        RecipeReport(
            recipe_id=recipe_id,
            reporter_user_id=reporter_user_id,
            reason=payload.reason,
            comment=payload.comment,
        )
    )

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise RecipeReportConflictError("You have already reported this recipe") from exc

    reports_count = db.execute(
        select(func.count(RecipeReport.id)).where(RecipeReport.recipe_id == recipe_id)
    ).scalar_one()
    recipe.reports_count = int(reports_count or 0)

    if recipe.reports_count >= 3:
        recipe.status = FoodStatus.pending
        recipe.is_listed = False

    db.commit()
    db.refresh(recipe)
    return recipe


def calculate_recipe_nutrients(recipe: Recipe) -> dict[str, Decimal]:
    total_grams = Decimal("0")
    total_kcal = Decimal("0")
    total_protein = Decimal("0")
    total_fat = Decimal("0")
    total_carbs = Decimal("0")

    for ingredient in recipe.ingredients:
        if ingredient.food is None:
            continue

        factor = ingredient.grams / HUNDRED_GRAMS
        total_grams += ingredient.grams
        total_kcal += ingredient.food.kcal * factor
        total_protein += ingredient.food.protein * factor
        total_fat += ingredient.food.fat * factor
        total_carbs += ingredient.food.carbs * factor

    servings_count = Decimal(recipe.servings_count)
    per_serving_kcal = total_kcal / servings_count
    per_serving_protein = total_protein / servings_count
    per_serving_fat = total_fat / servings_count
    per_serving_carbs = total_carbs / servings_count

    return {
        "total_grams": _quantize_nutrient(total_grams),
        "total_kcal": _quantize_nutrient(total_kcal),
        "total_protein": _quantize_nutrient(total_protein),
        "total_fat": _quantize_nutrient(total_fat),
        "total_carbs": _quantize_nutrient(total_carbs),
        "per_serving_kcal": _quantize_nutrient(per_serving_kcal),
        "per_serving_protein": _quantize_nutrient(per_serving_protein),
        "per_serving_fat": _quantize_nutrient(per_serving_fat),
        "per_serving_carbs": _quantize_nutrient(per_serving_carbs),
    }


def build_recipe_read(recipe: Recipe) -> RecipeRead:
    nutrients = calculate_recipe_nutrients(recipe)
    return RecipeRead.model_validate(
        {
            "id": recipe.id,
            "owner_user_id": recipe.owner_user_id,
            "name": recipe.name,
            "description": recipe.description,
            "servings_count": recipe.servings_count,
            "meal_types": recipe.meal_types,
            "source": recipe.source,
            "status": recipe.status,
            "reports_count": recipe.reports_count,
            "is_listed": recipe.is_listed,
            "created_at": recipe.created_at,
            "updated_at": recipe.updated_at,
            **nutrients,
        }
    )
