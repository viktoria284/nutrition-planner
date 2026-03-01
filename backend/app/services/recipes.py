from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recipe import Recipe
from app.schemas.recipes import RecipeCreate, RecipeUpdate


class RecipeNotFoundError(ValueError):
    pass


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


def list_my_recipes(db: Session, owner_id: int, limit: int = 50, offset: int = 0) -> list[Recipe]:
    return db.execute(
        select(Recipe)
        .where(Recipe.owner_user_id == owner_id)
        .order_by(Recipe.updated_at.desc(), Recipe.id.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()


def get_my_recipe_or_404(db: Session, owner_id: int, recipe_id: int) -> Recipe:
    recipe = db.execute(
        select(Recipe).where(
            Recipe.id == recipe_id,
            Recipe.owner_user_id == owner_id,
        )
    ).scalar_one_or_none()
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
