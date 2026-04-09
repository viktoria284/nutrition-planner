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
    RecipeReportCreate,
    RecipeUpdate,
)
from app.services.recipes import (
    RecipeNotEditableError,
    RecipeIngredientFoodNotFoundError,
    RecipeIngredientNotFoundError,
    RecipeIngredientServingMismatchError,
    RecipeNotFoundError,
    RecipePublishConflictError,
    RecipeReportConflictError,
    RecipeReportNotAllowedError,
    RecipeReportSelfError,
    RecipeWithdrawConflictError,
    RecipeWithdrawForbiddenError,
    add_ingredient,
    build_recipe_read,
    create_recipe,
    delete_ingredient,
    delete_my_recipe,
    get_accessible_recipe_by_id,
    get_my_recipe_or_404,
    list_accessible_recipes,
    publish_recipe,
    report_recipe,
    update_ingredient,
    update_my_recipe,
    withdraw_recipe,
)

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("", response_model=list[RecipeRead])
def get_recipes(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_public: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recipes = list_accessible_recipes(
        db,
        current_user.id,
        include_public=include_public,
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
    recipe = get_accessible_recipe_by_id(
        db,
        current_user.id,
        recipe_id,
        include_ingredients=True,
    )
    if not recipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
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
    except RecipeNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
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
    except RecipeNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{recipe_id}/publish", response_model=RecipeRead)
def publish_recipe_by_id(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        recipe = publish_recipe(db, current_user.id, recipe_id)
    except RecipePublishConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if not recipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")

    return build_recipe_read(recipe)


@router.post("/{recipe_id}/withdraw", response_model=RecipeRead)
def withdraw_recipe_by_id(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        recipe = withdraw_recipe(db, current_user.id, recipe_id)
    except RecipeWithdrawForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RecipeWithdrawConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if not recipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")

    return build_recipe_read(recipe)


@router.post("/{recipe_id}/report", response_model=RecipeRead)
def report_recipe_by_id(
    recipe_id: int,
    payload: RecipeReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        recipe = report_recipe(db, current_user.id, recipe_id, payload)
    except (RecipeReportSelfError, RecipeReportNotAllowedError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RecipeReportConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if not recipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")

    return build_recipe_read(recipe)


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
    except RecipeIngredientServingMismatchError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RecipeNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
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
    except RecipeIngredientServingMismatchError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RecipeNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
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
    except RecipeNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
