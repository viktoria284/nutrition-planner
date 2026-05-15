from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.recipes import (
    ALLOWED_MEAL_TYPES,
    RecipeCreate,
    RecipeFavoriteStateRead,
    RecipeIngredientCreate,
    RecipeIngredientRead,
    RecipeIngredientUpdate,
    RecipeNoteRead,
    RecipeNoteUpsert,
    RecipeRead,
    RecipeReportCreate,
    RecipeStepRead,
    RecipeStepsReplace,
    RecipeUpdate,
)
from app.services.recipes import (
    RecipeNoteBlankError,
    RecipeNotEditableError,
    RecipeIngredientFoodNotFoundError,
    RecipeIngredientNotFoundError,
    RecipeIngredientServingMismatchError,
    RecipeNotFoundError,
    RecipePublishConflictError,
    RecipeReportConflictError,
    RecipeReportNotAllowedError,
    RecipeReportSelfError,
    RecipeStepNotFoundError,
    RecipeWithdrawConflictError,
    RecipeWithdrawForbiddenError,
    add_ingredient,
    add_recipe_favorite,
    build_recipe_read,
    copy_accessible_recipe,
    create_recipe,
    delete_recipe_cover_image,
    delete_recipe_note,
    delete_recipe_step_image,
    delete_ingredient,
    delete_my_recipe,
    get_accessible_recipe_by_id,
    get_recipe_note,
    get_my_recipe_or_404,
    list_accessible_recipes,
    list_favorite_recipe_ids,
    list_recipe_steps,
    publish_recipe,
    replace_recipe_steps,
    report_recipe,
    remove_recipe_favorite,
    upload_recipe_cover_image,
    upload_recipe_step_image,
    upsert_recipe_note,
    update_ingredient,
    update_my_recipe,
    withdraw_recipe,
)

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("", response_model=list[RecipeRead])
def get_recipes(
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_public: bool = Query(default=False),
    favorite_only: bool = Query(default=False),
    meal_type: str | None = Query(default=None),
    min_cook_time_minutes: Annotated[int | None, Query(ge=1, le=1440)] = None,
    max_cook_time_minutes: Annotated[int | None, Query(ge=1, le=1440)] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    normalized_meal_type = meal_type.strip().lower() if meal_type else None
    if normalized_meal_type is not None and normalized_meal_type not in ALLOWED_MEAL_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid meal_type",
        )
    if (
        min_cook_time_minutes is not None
        and max_cook_time_minutes is not None
        and min_cook_time_minutes > max_cook_time_minutes
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="min_cook_time_minutes cannot be greater than max_cook_time_minutes",
        )

    recipes = list_accessible_recipes(
        db,
        current_user.id,
        include_public=include_public,
        favorite_only=favorite_only,
        limit=limit,
        offset=offset,
        meal_type=normalized_meal_type,
        min_cook_time_minutes=min_cook_time_minutes,
        max_cook_time_minutes=max_cook_time_minutes,
        include_ingredients=True,
    )
    favorite_ids = list_favorite_recipe_ids(
        db,
        user_id=current_user.id,
        recipe_ids={recipe.id for recipe in recipes},
    )
    return [build_recipe_read(recipe, is_favorite=recipe.id in favorite_ids) for recipe in recipes]


@router.post("", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
def post_recipe(
    payload: RecipeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recipe = create_recipe(db, current_user.id, payload)
    return build_recipe_read(recipe, is_favorite=False)


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
    favorite_ids = list_favorite_recipe_ids(
        db,
        user_id=current_user.id,
        recipe_ids={recipe.id},
    )
    return build_recipe_read(recipe, is_favorite=recipe.id in favorite_ids)


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
    favorite_ids = list_favorite_recipe_ids(
        db,
        user_id=current_user.id,
        recipe_ids={recipe.id},
    )
    return build_recipe_read(recipe, is_favorite=recipe.id in favorite_ids)


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

    favorite_ids = list_favorite_recipe_ids(
        db,
        user_id=current_user.id,
        recipe_ids={recipe.id},
    )
    return build_recipe_read(recipe, is_favorite=recipe.id in favorite_ids)


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

    favorite_ids = list_favorite_recipe_ids(
        db,
        user_id=current_user.id,
        recipe_ids={recipe.id},
    )
    return build_recipe_read(recipe, is_favorite=recipe.id in favorite_ids)


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

    favorite_ids = list_favorite_recipe_ids(
        db,
        user_id=current_user.id,
        recipe_ids={recipe.id},
    )
    return build_recipe_read(recipe, is_favorite=recipe.id in favorite_ids)


@router.get("/{recipe_id}/note", response_model=RecipeNoteRead)
def get_recipe_note_by_recipe_id(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recipe = get_accessible_recipe_by_id(
        db,
        current_user.id,
        recipe_id,
        include_ingredients=False,
    )
    if not recipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    recipe_note = get_recipe_note(db, current_user.id, recipe_id)
    return RecipeNoteRead(note=recipe_note.note if recipe_note else None)


@router.put("/{recipe_id}/note", response_model=RecipeNoteRead)
def put_recipe_note_by_recipe_id(
    recipe_id: int,
    payload: RecipeNoteUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        recipe_note = upsert_recipe_note(db, current_user.id, recipe_id, payload.note)
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    except RecipeNoteBlankError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return RecipeNoteRead(note=recipe_note.note)


@router.delete("/{recipe_id}/note", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe_note_by_recipe_id(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        delete_recipe_note(db, current_user.id, recipe_id)
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{recipe_id}/copy", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
def copy_recipe_by_id(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        copied_recipe = copy_accessible_recipe(db, current_user.id, recipe_id)
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    return build_recipe_read(copied_recipe, is_favorite=False)


@router.post("/{recipe_id}/cover-image", response_model=RecipeRead)
def post_recipe_cover_image(
    recipe_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        recipe = upload_recipe_cover_image(
            db,
            current_user.id,
            recipe_id,
            file,
        )
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    except RecipeNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        if "too large" in detail.lower():
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image is too large") from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc
    favorite_ids = list_favorite_recipe_ids(
        db,
        user_id=current_user.id,
        recipe_ids={recipe.id},
    )
    return build_recipe_read(recipe, is_favorite=recipe.id in favorite_ids)


@router.delete("/{recipe_id}/cover-image", response_model=RecipeRead)
def delete_recipe_cover_image_by_id(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        recipe = delete_recipe_cover_image(db, current_user.id, recipe_id)
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    except RecipeNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    favorite_ids = list_favorite_recipe_ids(
        db,
        user_id=current_user.id,
        recipe_ids={recipe.id},
    )
    return build_recipe_read(recipe, is_favorite=recipe.id in favorite_ids)


@router.post("/{recipe_id}/favorite", response_model=RecipeFavoriteStateRead)
def post_recipe_favorite(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        add_recipe_favorite(db, user_id=current_user.id, recipe_id=recipe_id)
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    return RecipeFavoriteStateRead(recipe_id=recipe_id, is_favorite=True)


@router.delete("/{recipe_id}/favorite", response_model=RecipeFavoriteStateRead)
def delete_recipe_favorite_by_id(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    remove_recipe_favorite(db, user_id=current_user.id, recipe_id=recipe_id)
    return RecipeFavoriteStateRead(recipe_id=recipe_id, is_favorite=False)


@router.get("/{recipe_id}/steps", response_model=list[RecipeStepRead])
def get_recipe_steps_by_id(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        steps = list_recipe_steps(db, current_user.id, recipe_id)
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    return [RecipeStepRead.model_validate(step) for step in steps]


@router.put("/{recipe_id}/steps", response_model=list[RecipeStepRead])
def put_recipe_steps_by_id(
    recipe_id: int,
    payload: RecipeStepsReplace,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        steps = replace_recipe_steps(db, current_user.id, recipe_id, payload)
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    except RecipeNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return [RecipeStepRead.model_validate(step) for step in steps]


@router.post("/{recipe_id}/steps/{step_id}/image", response_model=RecipeStepRead)
def post_recipe_step_image(
    recipe_id: int,
    step_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        step = upload_recipe_step_image(
            db,
            current_user.id,
            recipe_id,
            step_id,
            file,
        )
    except (RecipeNotFoundError, RecipeStepNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe step not found") from exc
    except RecipeNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        if "too large" in detail.lower():
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image is too large") from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc
    return RecipeStepRead.model_validate(step)


@router.delete("/{recipe_id}/steps/{step_id}/image", response_model=RecipeStepRead)
def delete_recipe_step_image_by_id(
    recipe_id: int,
    step_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        step = delete_recipe_step_image(db, current_user.id, recipe_id, step_id)
    except (RecipeNotFoundError, RecipeStepNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe step not found") from exc
    except RecipeNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return RecipeStepRead.model_validate(step)


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
