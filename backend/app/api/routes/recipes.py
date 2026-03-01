from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.recipes import RecipeCreate, RecipeRead, RecipeUpdate
from app.services.recipes import (
    RecipeNotFoundError,
    create_recipe,
    delete_my_recipe,
    get_my_recipe_or_404,
    list_my_recipes,
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
    return list_my_recipes(db, current_user.id, limit=limit, offset=offset)


@router.post("", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
def post_recipe(
    payload: RecipeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recipe = create_recipe(db, current_user.id, payload)
    return RecipeRead.model_validate(recipe)


@router.get("/{recipe_id}", response_model=RecipeRead)
def get_recipe_by_id(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        recipe = get_my_recipe_or_404(db, current_user.id, recipe_id)
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    return RecipeRead.model_validate(recipe)


@router.patch("/{recipe_id}", response_model=RecipeRead)
def patch_recipe_by_id(
    recipe_id: int,
    payload: RecipeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        recipe = update_my_recipe(db, current_user.id, recipe_id, payload)
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    return RecipeRead.model_validate(recipe)


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
