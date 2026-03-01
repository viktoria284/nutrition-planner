from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.recipe import Recipe, RecipeIngredient
from app.schemas.recipes import (
    RecipeCreate,
    RecipeIngredientCreate,
    RecipeIngredientUpdate,
    RecipeRead,
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


def _quantize_nutrient(value: Decimal) -> Decimal:
    return value.quantize(NUTRIENT_QUANT, rounding=ROUND_HALF_UP)


def create_recipe(db: Session, owner_id: int, data: RecipeCreate) -> Recipe:
    recipe = Recipe(
        owner_user_id=owner_id,
        name=data.name,
        description=data.description,
        servings_count=data.servings_count,
        meal_types=data.meal_types,
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


def update_my_recipe(db: Session, owner_id: int, recipe_id: int, data: RecipeUpdate) -> Recipe:
    recipe = get_my_recipe_or_404(db, owner_id, recipe_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(recipe, field, value)

    db.commit()
    db.refresh(recipe)
    return recipe


def delete_my_recipe(db: Session, owner_id: int, recipe_id: int) -> None:
    recipe = get_my_recipe_or_404(db, owner_id, recipe_id)
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
    ingredient = _get_recipe_ingredient_or_404(db, recipe.id, ingredient_id)
    db.delete(ingredient)
    db.commit()


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
            "created_at": recipe.created_at,
            "updated_at": recipe.updated_at,
            **nutrients,
        }
    )
