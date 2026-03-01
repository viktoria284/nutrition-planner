from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.recipes import (
    RecipeCreate,
    RecipeIngredientCreate,
    RecipeIngredientRead,
    RecipeIngredientUpdate,
    RecipeRead,
    RecipeUpdate,
)
from app.services.recipes import (
    RecipeIngredientFoodNotFoundError,
    RecipeIngredientNotFoundError,
    RecipeNotFoundError,
    add_ingredient,
    build_recipe_read,
    create_recipe,
    delete_ingredient,
    delete_my_recipe,
    get_my_recipe_or_404,
    list_my_recipes,
    update_ingredient,
    update_my_recipe,
)

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("", response_model=list[RecipeRead])
def get_recipes(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recipes = list_my_recipes(
        db,
        current_user.id,
        limit=limit,
        offset=offset,
        include_ingredients=True,
    )
    return [build_recipe_read(recipe) for recipe in recipes]


@router.post("", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
def post_recipe(
    payload: RecipeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recipe = create_recipe(db, current_user.id, payload)
    return build_recipe_read(recipe)


@router.get("/{recipe_id}", response_model=RecipeRead)
def get_recipe_by_id(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        recipe = get_my_recipe_or_404(
            db,
            current_user.id,
            recipe_id,
            include_ingredients=True,
        )
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    return build_recipe_read(recipe)


@router.patch("/{recipe_id}", response_model=RecipeRead)
def patch_recipe_by_id(
    recipe_id: int,
    payload: RecipeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        update_my_recipe(db, current_user.id, recipe_id, payload)
        recipe = get_my_recipe_or_404(
            db,
            current_user.id,
            recipe_id,
            include_ingredients=True,
        )
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    return build_recipe_read(recipe)


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe_by_id(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        delete_my_recipe(db, current_user.id, recipe_id)
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{recipe_id}/ingredients", response_model=RecipeIngredientRead, status_code=status.HTTP_201_CREATED)
def post_recipe_ingredient(
    recipe_id: int,
    payload: RecipeIngredientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        ingredient = add_ingredient(db, current_user.id, recipe_id, payload)
    except (RecipeNotFoundError, RecipeIngredientFoodNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingredient not found") from exc
    return RecipeIngredientRead.model_validate(ingredient)


@router.patch("/{recipe_id}/ingredients/{ingredient_id}", response_model=RecipeIngredientRead)
def patch_recipe_ingredient(
    recipe_id: int,
    ingredient_id: int,
    payload: RecipeIngredientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        ingredient = update_ingredient(db, current_user.id, recipe_id, ingredient_id, payload)
    except (RecipeNotFoundError, RecipeIngredientNotFoundError, RecipeIngredientFoodNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingredient not found") from exc
    return RecipeIngredientRead.model_validate(ingredient)


@router.delete("/{recipe_id}/ingredients/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe_ingredient(
    recipe_id: int,
    ingredient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        delete_ingredient(db, current_user.id, recipe_id, ingredient_id)
    except (RecipeNotFoundError, RecipeIngredientNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingredient not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
