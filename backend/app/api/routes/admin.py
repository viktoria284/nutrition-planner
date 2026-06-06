from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.permissions import require_admin, require_superadmin
from app.models.enums import FoodSource, FoodStatus
from app.models.user import User
from app.schemas.admin import (
    AdminContentOrigin,
    AdminFoodListItemRead,
    AdminFoodsQuery,
    AdminModerateRequest,
    AdminRecipeListItemRead,
    AdminRecipesQuery,
    AdminReportRead,
    AdminReportsQuery,
    AdminResolveReportRequest,
    AdminRoleUpdateRequest,
    AdminSummaryRead,
    AdminUserListItemRead,
    AdminUsersQuery,
)
from app.schemas.foods import FoodItemCreate, FoodItemRead, FoodItemUpdate
from app.schemas.recipes import (
    RecipeCreate,
    RecipeIngredientCreate,
    RecipeIngredientRead,
    RecipeIngredientUpdate,
    RecipeRead,
    RecipeStepRead,
    RecipeStepsReplace,
    RecipeUpdate,
)
from app.services.admin import (
    AdminModerationError,
    AdminNotFoundError,
    UnifiedReportRow,
    apply_resolution_side_effects_for_food,
    apply_resolution_side_effects_for_recipe,
    create_public_food_by_admin,
    create_public_recipe_by_admin,
    add_recipe_ingredient_by_admin,
    delete_recipe_cover_image_by_admin,
    delete_recipe_ingredient_by_admin,
    delete_recipe_step_image_by_admin,
    delete_food_by_admin,
    delete_recipe_by_admin,
    get_admin_summary,
    get_recipe_by_admin,
    list_admin_foods,
    list_admin_recipes,
    list_admin_reports,
    list_admin_users,
    moderate_food_by_admin,
    moderate_recipe_by_admin,
    replace_recipe_steps_by_admin,
    resolve_food_report,
    resolve_recipe_report,
    update_food_by_admin,
    update_recipe_ingredient_by_admin,
    update_recipe_by_admin,
    upload_recipe_cover_image_by_admin,
    upload_recipe_step_image_by_admin,
)
from app.services.recipes import build_recipe_read
from app.services.recipes import RecipeIngredientServingMismatchError
from app.services.users import RoleChangeError, set_user_role_by_superadmin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/summary", response_model=AdminSummaryRead)
def get_summary(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    summary = get_admin_summary(db)
    return AdminSummaryRead.model_validate(summary)


@router.get("/foods", response_model=list[AdminFoodListItemRead])
def get_admin_foods(
    q: str | None = None,
    source: FoodSource | None = None,
    origin: AdminContentOrigin = "all",
    status_value: FoodStatus | None = Query(default=None, alias="status"),
    is_listed: bool | None = None,
    reported_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    filters = AdminFoodsQuery(
        q=q,
        source=source,
        origin=origin,
        status=status_value,
        is_listed=is_listed,
        reported_only=reported_only,
        limit=limit,
        offset=offset,
    )
    foods = list_admin_foods(
        db,
        q=filters.q,
        source=filters.source,
        origin=filters.origin,
        status=filters.status,
        is_listed=filters.is_listed,
        reported_only=filters.reported_only,
        limit=filters.limit,
        offset=filters.offset,
    )
    response: list[AdminFoodListItemRead] = []
    for food in foods:
        owner = None
        if food.owner_user_id is not None:
            owner_row = db.get(User, food.owner_user_id)
            if owner_row is not None:
                owner = {"id": owner_row.id, "username": owner_row.username, "display_name": owner_row.display_name}
        response.append(
            AdminFoodListItemRead.model_validate(
                {
                    "id": food.id,
                    "name": food.name,
                    "brand": food.brand,
                    "category": food.category,
                    "kcal": food.kcal,
                    "protein": food.protein,
                    "fat": food.fat,
                    "carbs": food.carbs,
                    "fiber": food.fiber,
                    "source": food.source,
                    "status": food.status,
                    "is_listed": food.is_listed,
                    "reports_count": food.reports_count,
                    "owner": owner,
                    "created_at": food.created_at,
                    "updated_at": food.updated_at,
                }
            )
        )
    return response


@router.post("/foods", response_model=FoodItemRead, status_code=status.HTTP_201_CREATED)
def create_admin_food(
    payload: FoodItemCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    food = create_public_food_by_admin(db, data=payload)
    return FoodItemRead.model_validate(food)


@router.patch("/foods/{food_id}", response_model=FoodItemRead)
def update_admin_food(
    food_id: int,
    payload: FoodItemUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    try:
        food = update_food_by_admin(db, food_id=food_id, data=payload)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found") from exc
    return FoodItemRead.model_validate(food)


@router.delete("/foods/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_food(
    food_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    try:
        delete_food_by_admin(db, food_id=food_id)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/recipes", response_model=list[AdminRecipeListItemRead])
def get_admin_recipes(
    q: str | None = None,
    origin: AdminContentOrigin = "all",
    status_value: FoodStatus | None = Query(default=None, alias="status"),
    is_listed: bool | None = None,
    reported_only: bool = False,
    meal_type: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    filters = AdminRecipesQuery(
        q=q,
        origin=origin,
        status=status_value,
        is_listed=is_listed,
        reported_only=reported_only,
        meal_type=meal_type,
        limit=limit,
        offset=offset,
    )
    recipes = list_admin_recipes(
        db,
        q=filters.q,
        origin=filters.origin,
        status=filters.status,
        is_listed=filters.is_listed,
        reported_only=filters.reported_only,
        meal_type=filters.meal_type,
        limit=filters.limit,
        offset=filters.offset,
    )
    response: list[AdminRecipeListItemRead] = []
    for recipe in recipes:
        owner = None
        if recipe.owner_user_id is not None:
            owner_row = db.get(User, recipe.owner_user_id)
            if owner_row is not None:
                owner = {"id": owner_row.id, "username": owner_row.username, "display_name": owner_row.display_name}
        response.append(
            AdminRecipeListItemRead.model_validate(
                {
                    "id": recipe.id,
                    "name": recipe.name,
                    "description": recipe.description,
                    "instructions": recipe.instructions,
                    "servings_count": recipe.servings_count,
                    "cook_time_minutes": recipe.cook_time_minutes,
                    "source": recipe.source,
                    "status": recipe.status,
                    "is_listed": recipe.is_listed,
                    "meal_types": recipe.meal_types,
                    "reports_count": recipe.reports_count,
                    "owner": owner,
                    "created_at": recipe.created_at,
                    "updated_at": recipe.updated_at,
                }
            )
        )
    return response


@router.get("/recipes/{recipe_id}", response_model=RecipeRead)
def get_admin_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    try:
        recipe = get_recipe_by_admin(db, recipe_id=recipe_id)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    return build_recipe_read(recipe)


@router.post("/recipes", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
def create_admin_recipe(
    payload: RecipeCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    recipe = create_public_recipe_by_admin(db, data=payload)
    return build_recipe_read(recipe)


@router.post("/recipes/{recipe_id}/ingredients", response_model=RecipeIngredientRead, status_code=status.HTTP_201_CREATED)
def create_admin_recipe_ingredient(
    recipe_id: int,
    payload: RecipeIngredientCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    try:
        ingredient = add_recipe_ingredient_by_admin(db, recipe_id=recipe_id, data=payload)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RecipeIngredientServingMismatchError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return RecipeIngredientRead.model_validate(ingredient)


@router.patch("/recipes/{recipe_id}/ingredients/{ingredient_id}", response_model=RecipeIngredientRead)
def patch_admin_recipe_ingredient(
    recipe_id: int,
    ingredient_id: int,
    payload: RecipeIngredientUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    try:
        ingredient = update_recipe_ingredient_by_admin(db, recipe_id=recipe_id, ingredient_id=ingredient_id, data=payload)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RecipeIngredientServingMismatchError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return RecipeIngredientRead.model_validate(ingredient)


@router.delete("/recipes/{recipe_id}/ingredients/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_recipe_ingredient(
    recipe_id: int,
    ingredient_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    try:
        delete_recipe_ingredient_by_admin(db, recipe_id=recipe_id, ingredient_id=ingredient_id)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/recipes/{recipe_id}/steps", response_model=list[RecipeStepRead])
def put_admin_recipe_steps(
    recipe_id: int,
    payload: RecipeStepsReplace,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    try:
        steps = replace_recipe_steps_by_admin(db, recipe_id=recipe_id, payload=payload)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [RecipeStepRead.model_validate(step) for step in steps]


@router.post("/recipes/{recipe_id}/cover-image", response_model=RecipeRead)
def post_admin_recipe_cover_image(
    recipe_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    try:
        recipe = upload_recipe_cover_image_by_admin(db, recipe_id=recipe_id, upload_file=file)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    except ValueError as exc:
        detail = str(exc)
        if "too large" in detail.lower():
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image is too large") from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc
    return build_recipe_read(recipe)


@router.delete("/recipes/{recipe_id}/cover-image", response_model=RecipeRead)
def delete_admin_recipe_cover_image(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    try:
        recipe = delete_recipe_cover_image_by_admin(db, recipe_id=recipe_id)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    return build_recipe_read(recipe)


@router.post("/recipes/{recipe_id}/steps/{step_id}/image", response_model=RecipeStepRead)
def post_admin_recipe_step_image(
    recipe_id: int,
    step_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    try:
        step = upload_recipe_step_image_by_admin(db, recipe_id=recipe_id, step_id=step_id, upload_file=file)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe step not found") from exc
    except ValueError as exc:
        detail = str(exc)
        if "too large" in detail.lower():
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image is too large") from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc
    return RecipeStepRead.model_validate(step)


@router.delete("/recipes/{recipe_id}/steps/{step_id}/image", response_model=RecipeStepRead)
def delete_admin_recipe_step_image(
    recipe_id: int,
    step_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    try:
        step = delete_recipe_step_image_by_admin(db, recipe_id=recipe_id, step_id=step_id)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe step not found") from exc
    return RecipeStepRead.model_validate(step)


@router.patch("/recipes/{recipe_id}", response_model=RecipeRead)
def update_admin_recipe(
    recipe_id: int,
    payload: RecipeUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    try:
        recipe = update_recipe_by_admin(db, recipe_id=recipe_id, data=payload)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    return build_recipe_read(recipe)


@router.delete("/recipes/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    try:
        delete_recipe_by_admin(db, recipe_id=recipe_id)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/foods/{food_id}/moderate", response_model=FoodItemRead)
def moderate_food_endpoint(
    food_id: int,
    payload: AdminModerateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    try:
        food = moderate_food_by_admin(db, food_id=food_id, action=payload.action)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AdminModerationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return FoodItemRead.model_validate(food)


@router.put("/foods/{food_id}/moderate", response_model=FoodItemRead)
def moderate_food_endpoint_legacy(
    food_id: int,
    action: Literal["approve", "hide", "reject", "restore"] = Query(...),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    try:
        food = moderate_food_by_admin(db, food_id=food_id, action=action)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AdminModerationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return FoodItemRead.model_validate(food)


@router.post("/recipes/{recipe_id}/moderate", response_model=RecipeRead)
def moderate_recipe_endpoint(
    recipe_id: int,
    payload: AdminModerateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    try:
        recipe = moderate_recipe_by_admin(db, recipe_id=recipe_id, action=payload.action)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AdminModerationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return build_recipe_read(recipe)


@router.get("/reports", response_model=list[AdminReportRead])
def get_admin_reports(
    target_type: Literal["food", "recipe", "all"] = "all",
    only_open: bool = True,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    filters = AdminReportsQuery(target_type=target_type, only_open=only_open, limit=limit, offset=offset)
    rows = list_admin_reports(
        db,
        target_type=filters.target_type,
        only_open=filters.only_open,
        limit=filters.limit,
        offset=filters.offset,
    )
    return [_to_admin_report_read(item) for item in rows]


@router.post("/reports/foods/{report_id}/resolve", response_model=AdminReportRead)
def resolve_food_report_endpoint(
    report_id: int,
    payload: AdminResolveReportRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    try:
        report = resolve_food_report(
            db,
            report_id=report_id,
            admin_user_id=current_admin.id,
            resolution=payload.resolution,
            comment=payload.comment,
        )
        apply_resolution_side_effects_for_food(db, food_id=report.food_id, resolution=payload.resolution)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    rows = list_admin_reports(db, target_type="food", only_open=False, limit=1000, offset=0)
    resolved_row = next((row for row in rows if row.id == report_id), None)
    if resolved_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food report not found")
    return _to_admin_report_read(resolved_row)


@router.post("/reports/recipes/{report_id}/resolve", response_model=AdminReportRead)
def resolve_recipe_report_endpoint(
    report_id: int,
    payload: AdminResolveReportRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    try:
        report = resolve_recipe_report(
            db,
            report_id=report_id,
            admin_user_id=current_admin.id,
            resolution=payload.resolution,
            comment=payload.comment,
        )
        apply_resolution_side_effects_for_recipe(db, recipe_id=report.recipe_id, resolution=payload.resolution)
    except AdminNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    rows = list_admin_reports(db, target_type="recipe", only_open=False, limit=1000, offset=0)
    resolved_row = next((row for row in rows if row.id == report_id), None)
    if resolved_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe report not found")
    return _to_admin_report_read(resolved_row)


@router.get("/users", response_model=list[AdminUserListItemRead])
def get_admin_users(
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    _ = current_admin
    filters = AdminUsersQuery(q=q, limit=limit, offset=offset)
    users = list_admin_users(db, q=filters.q, limit=filters.limit, offset=filters.offset)
    return [AdminUserListItemRead.model_validate(item) for item in users]


@router.patch("/users/{user_id}/role", response_model=AdminUserListItemRead)
def update_admin_user_role(
    user_id: int,
    payload: AdminRoleUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_superadmin),
):
    try:
        user = set_user_role_by_superadmin(
            db,
            actor_user_id=current_admin.id,
            target_user_id=user_id,
            role=payload.role,
        )
    except RoleChangeError as exc:
        message = str(exc)
        if message == "User not found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message) from exc

    users = list_admin_users(db, q=user.email, limit=1, offset=0)
    row = next((item for item in users if item["id"] == user.id), None)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return AdminUserListItemRead.model_validate(row)


def _to_admin_report_read(item: UnifiedReportRow) -> AdminReportRead:
    reporter = {
        "id": item.reporter_user_id,
        "username": item.reporter_username,
        "display_name": item.reporter_display_name,
    }
    resolved_by = None
    if item.resolved_by_admin_id is not None:
        resolved_by = {
            "id": item.resolved_by_admin_id,
            "username": item.resolved_by_admin_username or "admin",
            "display_name": item.resolved_by_admin_display_name,
        }
    return AdminReportRead.model_validate(
        {
            "id": item.id,
            "target_type": item.target_type,
            "target_id": item.target_id,
            "target_name": item.target_name,
            "reporter": reporter,
            "reason": item.reason,
            "comment": item.comment,
            "created_at": item.created_at,
            "resolved_at": item.resolved_at,
            "resolution": item.resolution,
            "resolved_by_admin": resolved_by,
            "admin_comment": item.admin_comment,
        }
    )
