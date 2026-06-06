from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import and_, func, literal, or_, select
from sqlalchemy.orm import Session

from app.models.enums import FoodSource, FoodStatus
from app.models.foods import FoodItem, FoodReport
from app.models.plan import Plan
from app.models.profile import Profile
from app.models.recipe import Recipe, RecipeIngredient, RecipeReport, RecipeStep
from app.models.user import User
from app.schemas.foods import FoodItemCreate, FoodItemUpdate
from app.schemas.recipes import RecipeCreate, RecipeIngredientCreate, RecipeIngredientUpdate, RecipeStepsReplace, RecipeUpdate
from app.services.media import maybe_delete_media_file, save_uploaded_recipe_image
from app.services.recipes import _resolve_ingredient_measurement


class AdminNotFoundError(ValueError):
    pass


class AdminModerationError(ValueError):
    pass


class AdminReportResolutionError(ValueError):
    pass


@dataclass
class UnifiedReportRow:
    id: int
    target_type: str
    target_id: int
    target_name: str
    reporter_user_id: int
    reporter_username: str
    reporter_display_name: str | None
    reason: str | None
    comment: str | None
    created_at: datetime
    resolved_at: datetime | None
    resolution: str | None
    resolved_by_admin_id: int | None
    resolved_by_admin_username: str | None
    resolved_by_admin_display_name: str | None
    admin_comment: str | None


def _normalize_optional_query(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def get_admin_summary(db: Session) -> dict[str, int]:
    total_users = int(db.execute(select(func.count(User.id))).scalar_one() or 0)
    total_foods = int(db.execute(select(func.count(FoodItem.id))).scalar_one() or 0)
    total_recipes = int(db.execute(select(func.count(Recipe.id))).scalar_one() or 0)

    public_foods = int(
        db.execute(
            select(func.count(FoodItem.id)).where(
                FoodItem.source.in_([FoodSource.community, FoodSource.verified]),
                FoodItem.status == FoodStatus.approved,
                FoodItem.is_listed.is_(True),
            )
        ).scalar_one()
        or 0
    )
    public_recipes = int(
        db.execute(
            select(func.count(Recipe.id)).where(
                Recipe.source == FoodSource.community,
                Recipe.status == FoodStatus.approved,
                Recipe.is_listed.is_(True),
            )
        ).scalar_one()
        or 0
    )

    pending_foods = int(
        db.execute(select(func.count(FoodItem.id)).where(FoodItem.status == FoodStatus.pending)).scalar_one() or 0
    )
    pending_recipes = int(
        db.execute(select(func.count(Recipe.id)).where(Recipe.status == FoodStatus.pending)).scalar_one() or 0
    )

    open_food_reports = int(
        db.execute(select(func.count(FoodReport.id)).where(FoodReport.resolved_at.is_(None))).scalar_one() or 0
    )
    open_recipe_reports = int(
        db.execute(select(func.count(RecipeReport.id)).where(RecipeReport.resolved_at.is_(None))).scalar_one() or 0
    )

    return {
        "total_users": total_users,
        "total_foods": total_foods,
        "total_recipes": total_recipes,
        "public_foods": public_foods,
        "public_recipes": public_recipes,
        "pending_or_under_review_foods": pending_foods,
        "pending_or_under_review_recipes": pending_recipes,
        "open_food_reports": open_food_reports,
        "open_recipe_reports": open_recipe_reports,
    }


def list_admin_foods(
    db: Session,
    *,
    q: str | None,
    source: FoodSource | None,
    origin: str,
    status: FoodStatus | None,
    is_listed: bool | None,
    reported_only: bool,
    limit: int,
    offset: int,
) -> list[FoodItem]:
    stmt = select(FoodItem).order_by(FoodItem.updated_at.desc(), FoodItem.id.desc())

    q_normalized = _normalize_optional_query(q)
    if q_normalized:
        like_pattern = f"%{q_normalized.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(FoodItem.name).like(like_pattern),
                func.lower(func.coalesce(FoodItem.brand, "")).like(like_pattern),
            )
        )
    if source is not None:
        stmt = stmt.where(FoodItem.source == source)
    if origin == "system":
        stmt = stmt.where(FoodItem.owner_user_id.is_(None))
    elif origin == "user":
        stmt = stmt.where(FoodItem.owner_user_id.is_not(None), FoodItem.source == FoodSource.community)
    if status is not None:
        stmt = stmt.where(FoodItem.status == status)
    if is_listed is not None:
        stmt = stmt.where(FoodItem.is_listed.is_(is_listed))
    if reported_only:
        stmt = stmt.where(FoodItem.reports_count > 0)

    stmt = stmt.limit(limit).offset(offset)
    return db.execute(stmt).scalars().all()


def list_admin_recipes(
    db: Session,
    *,
    q: str | None,
    origin: str,
    status: FoodStatus | None,
    is_listed: bool | None,
    reported_only: bool,
    meal_type: str | None,
    limit: int,
    offset: int,
) -> list[Recipe]:
    stmt = select(Recipe).order_by(Recipe.updated_at.desc(), Recipe.id.desc())

    q_normalized = _normalize_optional_query(q)
    if q_normalized:
        like_pattern = f"%{q_normalized.lower()}%"
        stmt = stmt.where(func.lower(Recipe.name).like(like_pattern))
    if origin == "system":
        stmt = stmt.where(Recipe.owner_user_id.is_(None))
    elif origin == "user":
        stmt = stmt.where(Recipe.owner_user_id.is_not(None), Recipe.source == FoodSource.community)
    if status is not None:
        stmt = stmt.where(Recipe.status == status)
    if is_listed is not None:
        stmt = stmt.where(Recipe.is_listed.is_(is_listed))
    if reported_only:
        stmt = stmt.where(Recipe.reports_count > 0)
    if meal_type:
        mt = meal_type.strip().lower()
        stmt = stmt.where(Recipe.meal_types.contains([mt]))

    stmt = stmt.limit(limit).offset(offset)
    return db.execute(stmt).scalars().all()


def moderate_food_by_admin(
    db: Session,
    *,
    food_id: int,
    action: str,
) -> FoodItem:
    food = db.execute(select(FoodItem).where(FoodItem.id == food_id)).scalar_one_or_none()
    if food is None:
        raise AdminNotFoundError("Food not found")

    if food.source not in {FoodSource.community, FoodSource.verified}:
        raise AdminModerationError("Only public foods can be moderated")

    if action == "approve":
        food.status = FoodStatus.approved
        food.is_listed = True
    elif action == "hide":
        food.is_listed = False
    elif action == "reject":
        food.status = FoodStatus.rejected
        food.is_listed = False
    elif action == "restore":
        food.status = FoodStatus.approved
        food.is_listed = True
    else:
        raise AdminModerationError("Invalid moderation action")

    db.commit()
    db.refresh(food)
    return food


def create_public_food_by_admin(db: Session, *, data: FoodItemCreate) -> FoodItem:
    food = FoodItem(
        name=data.name,
        brand=data.brand,
        category=data.category,
        kcal=data.kcal,
        protein=data.protein,
        fat=data.fat,
        carbs=data.carbs,
        fiber=data.fiber,
        source=FoodSource.verified,
        status=FoodStatus.approved,
        owner_user_id=None,
        is_listed=True,
        reports_count=0,
    )
    db.add(food)
    db.commit()
    db.refresh(food)
    return food


def update_food_by_admin(db: Session, *, food_id: int, data: FoodItemUpdate) -> FoodItem:
    food = db.execute(select(FoodItem).where(FoodItem.id == food_id)).scalar_one_or_none()
    if food is None:
        raise AdminNotFoundError("Food not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(food, field, value)

    db.commit()
    db.refresh(food)
    return food


def delete_food_by_admin(db: Session, *, food_id: int) -> None:
    food = db.execute(select(FoodItem).where(FoodItem.id == food_id)).scalar_one_or_none()
    if food is None:
        raise AdminNotFoundError("Food not found")

    db.delete(food)
    db.commit()


def moderate_recipe_by_admin(
    db: Session,
    *,
    recipe_id: int,
    action: str,
) -> Recipe:
    recipe = db.execute(select(Recipe).where(Recipe.id == recipe_id)).scalar_one_or_none()
    if recipe is None:
        raise AdminNotFoundError("Recipe not found")

    if recipe.source != FoodSource.community:
        raise AdminModerationError("Only public recipes can be moderated")

    if action == "approve":
        recipe.status = FoodStatus.approved
        recipe.is_listed = True
    elif action == "hide":
        recipe.is_listed = False
    elif action == "reject":
        recipe.status = FoodStatus.rejected
        recipe.is_listed = False
    elif action == "restore":
        recipe.status = FoodStatus.approved
        recipe.is_listed = True
    else:
        raise AdminModerationError("Invalid moderation action")

    db.commit()
    db.refresh(recipe)
    return recipe


def create_public_recipe_by_admin(db: Session, *, data: RecipeCreate) -> Recipe:
    recipe = Recipe(
        owner_user_id=None,
        name=data.name,
        description=data.description,
        instructions=data.instructions,
        image_url=data.image_url,
        servings_count=data.servings_count,
        meal_types=data.meal_types,
        cook_time_minutes=data.cook_time_minutes,
        source=FoodSource.community,
        status=FoodStatus.approved,
        is_listed=True,
        reports_count=0,
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


def get_recipe_by_admin(db: Session, *, recipe_id: int) -> Recipe:
    recipe = db.execute(select(Recipe).where(Recipe.id == recipe_id)).scalar_one_or_none()
    if recipe is None:
        raise AdminNotFoundError("Recipe not found")
    return recipe


def update_recipe_by_admin(db: Session, *, recipe_id: int, data: RecipeUpdate) -> Recipe:
    recipe = get_recipe_by_admin(db, recipe_id=recipe_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(recipe, field, value)

    db.commit()
    db.refresh(recipe)
    return recipe


def add_recipe_ingredient_by_admin(db: Session, *, recipe_id: int, data: RecipeIngredientCreate) -> RecipeIngredient:
    recipe = get_recipe_by_admin(db, recipe_id=recipe_id)
    food = db.execute(select(FoodItem).where(FoodItem.id == data.food_id)).scalar_one_or_none()
    if food is None:
        raise AdminNotFoundError("Food not found")

    grams, serving_id, multiplier = _resolve_ingredient_measurement(
        db,
        food_id=data.food_id,
        grams=data.grams,
        serving_id=data.serving_id,
        multiplier=data.multiplier,
    )
    ingredient = RecipeIngredient(
        recipe_id=recipe.id,
        food_id=data.food_id,
        grams=grams,
        serving_id=serving_id,
        multiplier=multiplier,
    )
    db.add(ingredient)
    db.commit()
    db.refresh(ingredient)
    return ingredient


def update_recipe_ingredient_by_admin(
    db: Session,
    *,
    recipe_id: int,
    ingredient_id: int,
    data: RecipeIngredientUpdate,
) -> RecipeIngredient:
    get_recipe_by_admin(db, recipe_id=recipe_id)
    ingredient = db.execute(
        select(RecipeIngredient).where(
            RecipeIngredient.id == ingredient_id,
            RecipeIngredient.recipe_id == recipe_id,
        )
    ).scalar_one_or_none()
    if ingredient is None:
        raise AdminNotFoundError("Ingredient not found")

    update_data = data.model_dump(exclude_unset=True)
    next_food_id = update_data.get("food_id", ingredient.food_id)
    if "food_id" in update_data:
        food = db.execute(select(FoodItem).where(FoodItem.id == next_food_id)).scalar_one_or_none()
        if food is None:
            raise AdminNotFoundError("Food not found")

    next_grams = ingredient.grams
    next_serving_id = ingredient.serving_id
    next_multiplier = ingredient.multiplier

    has_explicit_grams = "grams" in update_data and update_data["grams"] is not None
    has_serving_payload = "serving_id" in update_data or "multiplier" in update_data
    if has_explicit_grams:
        next_grams = update_data["grams"]
        next_serving_id = None
        next_multiplier = None
    elif has_serving_payload:
        next_serving_id = update_data.get("serving_id", next_serving_id)
        next_multiplier = update_data.get("multiplier", next_multiplier)
        if next_serving_id is None:
            next_multiplier = None
        else:
            next_grams, next_serving_id, next_multiplier = _resolve_ingredient_measurement(
                db,
                food_id=next_food_id,
                grams=None,
                serving_id=next_serving_id,
                multiplier=next_multiplier,
            )

    ingredient.food_id = next_food_id
    ingredient.grams = next_grams
    ingredient.serving_id = next_serving_id
    ingredient.multiplier = next_multiplier

    db.commit()
    db.refresh(ingredient)
    return ingredient


def delete_recipe_ingredient_by_admin(db: Session, *, recipe_id: int, ingredient_id: int) -> None:
    get_recipe_by_admin(db, recipe_id=recipe_id)
    ingredient = db.execute(
        select(RecipeIngredient).where(
            RecipeIngredient.id == ingredient_id,
            RecipeIngredient.recipe_id == recipe_id,
        )
    ).scalar_one_or_none()
    if ingredient is None:
        raise AdminNotFoundError("Ingredient not found")
    db.delete(ingredient)
    db.commit()


def replace_recipe_steps_by_admin(db: Session, *, recipe_id: int, payload: RecipeStepsReplace) -> list[RecipeStep]:
    get_recipe_by_admin(db, recipe_id=recipe_id)
    existing_steps = db.execute(select(RecipeStep).where(RecipeStep.recipe_id == recipe_id)).scalars().all()
    existing_by_id = {step.id: step for step in existing_steps}
    used_ids: set[int] = set()

    referenced_existing_ids = [
        step_input.id
        for step_input in payload.steps
        if step_input.id is not None and step_input.id in existing_by_id
    ]
    temporary_start_position = max(
        len(existing_steps) + len(payload.steps) + 1,
        max((step.position for step in existing_steps), default=0) + len(existing_steps) + 1,
    )
    for offset, step_id in enumerate(referenced_existing_ids):
        existing_by_id[step_id].position = temporary_start_position + offset
    db.flush()

    for index, step_input in enumerate(payload.steps, start=1):
        if step_input.id is not None and step_input.id in existing_by_id:
            step = existing_by_id[step_input.id]
            step.position = index
            step.text = step_input.text
            step.note = step_input.note
            used_ids.add(step.id)
            continue
        db.add(
            RecipeStep(
                recipe_id=recipe_id,
                position=index,
                text=step_input.text,
                note=step_input.note,
                image_url=None,
            )
        )

    for step in existing_steps:
        if step.id not in used_ids:
            maybe_delete_media_file(step.image_url)
            db.delete(step)

    db.commit()
    return db.execute(
        select(RecipeStep)
        .where(RecipeStep.recipe_id == recipe_id)
        .order_by(RecipeStep.position.asc(), RecipeStep.id.asc())
    ).scalars().all()


def upload_recipe_cover_image_by_admin(db: Session, *, recipe_id: int, upload_file) -> Recipe:
    recipe = get_recipe_by_admin(db, recipe_id=recipe_id)
    old_image_url = recipe.image_url
    recipe.image_url = save_uploaded_recipe_image(upload_file)
    db.commit()
    db.refresh(recipe)
    maybe_delete_media_file(old_image_url)
    return recipe


def delete_recipe_cover_image_by_admin(db: Session, *, recipe_id: int) -> Recipe:
    recipe = get_recipe_by_admin(db, recipe_id=recipe_id)
    old_image_url = recipe.image_url
    recipe.image_url = None
    db.commit()
    db.refresh(recipe)
    maybe_delete_media_file(old_image_url)
    return recipe


def _get_recipe_step_by_admin(db: Session, *, recipe_id: int, step_id: int) -> RecipeStep:
    get_recipe_by_admin(db, recipe_id=recipe_id)
    step = db.execute(
        select(RecipeStep).where(
            RecipeStep.id == step_id,
            RecipeStep.recipe_id == recipe_id,
        )
    ).scalar_one_or_none()
    if step is None:
        raise AdminNotFoundError("Recipe step not found")
    return step


def upload_recipe_step_image_by_admin(db: Session, *, recipe_id: int, step_id: int, upload_file) -> RecipeStep:
    step = _get_recipe_step_by_admin(db, recipe_id=recipe_id, step_id=step_id)
    old_image_url = step.image_url
    step.image_url = save_uploaded_recipe_image(upload_file)
    db.commit()
    db.refresh(step)
    maybe_delete_media_file(old_image_url)
    return step


def delete_recipe_step_image_by_admin(db: Session, *, recipe_id: int, step_id: int) -> RecipeStep:
    step = _get_recipe_step_by_admin(db, recipe_id=recipe_id, step_id=step_id)
    old_image_url = step.image_url
    step.image_url = None
    db.commit()
    db.refresh(step)
    maybe_delete_media_file(old_image_url)
    return step


def delete_recipe_by_admin(db: Session, *, recipe_id: int) -> None:
    recipe = get_recipe_by_admin(db, recipe_id=recipe_id)

    db.delete(recipe)
    db.commit()


def list_admin_reports(
    db: Session,
    *,
    target_type: str,
    only_open: bool,
    limit: int,
    offset: int,
) -> list[UnifiedReportRow]:
    food_query = (
        select(
            FoodReport.id.label("id"),
            literal("food").label("target_type"),
            FoodReport.food_id.label("target_id"),
            FoodItem.name.label("target_name"),
            FoodReport.reporter_user_id.label("reporter_user_id"),
            User.username.label("reporter_username"),
            User.display_name.label("reporter_display_name"),
            FoodReport.reason.label("reason"),
            literal(None).label("comment"),
            FoodReport.created_at.label("created_at"),
            FoodReport.resolved_at.label("resolved_at"),
            FoodReport.resolution.label("resolution"),
            FoodReport.resolved_by_admin_id.label("resolved_by_admin_id"),
            literal(None).label("resolved_by_admin_username"),
            literal(None).label("resolved_by_admin_display_name"),
            FoodReport.admin_comment.label("admin_comment"),
        )
        .join(FoodItem, FoodItem.id == FoodReport.food_id)
        .join(User, User.id == FoodReport.reporter_user_id)
    )
    food_admin_alias = User.__table__.alias("food_admin")
    food_query = food_query.outerjoin(food_admin_alias, food_admin_alias.c.id == FoodReport.resolved_by_admin_id).with_only_columns(
        FoodReport.id.label("id"),
        literal("food").label("target_type"),
        FoodReport.food_id.label("target_id"),
        FoodItem.name.label("target_name"),
        FoodReport.reporter_user_id.label("reporter_user_id"),
        User.username.label("reporter_username"),
        User.display_name.label("reporter_display_name"),
        FoodReport.reason.label("reason"),
        literal(None).label("comment"),
        FoodReport.created_at.label("created_at"),
        FoodReport.resolved_at.label("resolved_at"),
        FoodReport.resolution.label("resolution"),
        FoodReport.resolved_by_admin_id.label("resolved_by_admin_id"),
        food_admin_alias.c.username.label("resolved_by_admin_username"),
        food_admin_alias.c.display_name.label("resolved_by_admin_display_name"),
        FoodReport.admin_comment.label("admin_comment"),
    )

    recipe_query = (
        select(
            RecipeReport.id.label("id"),
            literal("recipe").label("target_type"),
            RecipeReport.recipe_id.label("target_id"),
            Recipe.name.label("target_name"),
            RecipeReport.reporter_user_id.label("reporter_user_id"),
            User.username.label("reporter_username"),
            User.display_name.label("reporter_display_name"),
            RecipeReport.reason.label("reason"),
            RecipeReport.comment.label("comment"),
            RecipeReport.created_at.label("created_at"),
            RecipeReport.resolved_at.label("resolved_at"),
            RecipeReport.resolution.label("resolution"),
            RecipeReport.resolved_by_admin_id.label("resolved_by_admin_id"),
            literal(None).label("resolved_by_admin_username"),
            literal(None).label("resolved_by_admin_display_name"),
            RecipeReport.admin_comment.label("admin_comment"),
        )
        .join(Recipe, Recipe.id == RecipeReport.recipe_id)
        .join(User, User.id == RecipeReport.reporter_user_id)
    )
    recipe_admin_alias = User.__table__.alias("recipe_admin")
    recipe_query = recipe_query.outerjoin(recipe_admin_alias, recipe_admin_alias.c.id == RecipeReport.resolved_by_admin_id).with_only_columns(
        RecipeReport.id.label("id"),
        literal("recipe").label("target_type"),
        RecipeReport.recipe_id.label("target_id"),
        Recipe.name.label("target_name"),
        RecipeReport.reporter_user_id.label("reporter_user_id"),
        User.username.label("reporter_username"),
        User.display_name.label("reporter_display_name"),
        RecipeReport.reason.label("reason"),
        RecipeReport.comment.label("comment"),
        RecipeReport.created_at.label("created_at"),
        RecipeReport.resolved_at.label("resolved_at"),
        RecipeReport.resolution.label("resolution"),
        RecipeReport.resolved_by_admin_id.label("resolved_by_admin_id"),
        recipe_admin_alias.c.username.label("resolved_by_admin_username"),
        recipe_admin_alias.c.display_name.label("resolved_by_admin_display_name"),
        RecipeReport.admin_comment.label("admin_comment"),
    )

    rows = []
    if target_type in {"all", "food"}:
        food_rows = db.execute(food_query).all()
        rows.extend(food_rows)
    if target_type in {"all", "recipe"}:
        recipe_rows = db.execute(recipe_query).all()
        rows.extend(recipe_rows)

    normalized_rows = [
        UnifiedReportRow(
            id=int(row.id),
            target_type=str(row.target_type),
            target_id=int(row.target_id),
            target_name=str(row.target_name),
            reporter_user_id=int(row.reporter_user_id),
            reporter_username=str(row.reporter_username),
            reporter_display_name=row.reporter_display_name,
            reason=row.reason,
            comment=row.comment,
            created_at=row.created_at,
            resolved_at=row.resolved_at,
            resolution=row.resolution,
            resolved_by_admin_id=row.resolved_by_admin_id,
            resolved_by_admin_username=row.resolved_by_admin_username,
            resolved_by_admin_display_name=row.resolved_by_admin_display_name,
            admin_comment=row.admin_comment,
        )
        for row in rows
    ]

    if only_open:
        normalized_rows = [row for row in normalized_rows if row.resolved_at is None]

    normalized_rows.sort(key=lambda item: (item.created_at, item.target_type, item.id), reverse=True)
    return normalized_rows[offset : offset + limit]


def resolve_food_report(
    db: Session,
    *,
    report_id: int,
    admin_user_id: int,
    resolution: str,
    comment: str | None,
) -> FoodReport:
    report = db.execute(select(FoodReport).where(FoodReport.id == report_id)).scalar_one_or_none()
    if report is None:
        raise AdminNotFoundError("Food report not found")

    report.resolved_at = datetime.now(timezone.utc)
    report.resolved_by_admin_id = admin_user_id
    report.resolution = resolution
    report.admin_comment = comment
    db.commit()
    db.refresh(report)
    return report


def resolve_recipe_report(
    db: Session,
    *,
    report_id: int,
    admin_user_id: int,
    resolution: str,
    comment: str | None,
) -> RecipeReport:
    report = db.execute(select(RecipeReport).where(RecipeReport.id == report_id)).scalar_one_or_none()
    if report is None:
        raise AdminNotFoundError("Recipe report not found")

    report.resolved_at = datetime.now(timezone.utc)
    report.resolved_by_admin_id = admin_user_id
    report.resolution = resolution
    report.admin_comment = comment
    db.commit()
    db.refresh(report)
    return report


def list_admin_users(
    db: Session,
    *,
    q: str | None,
    limit: int,
    offset: int,
) -> list[dict]:
    q_normalized = _normalize_optional_query(q)
    profile_count_subq = (
        select(func.count(Profile.id))
        .where(Profile.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    recipe_count_subq = (
        select(func.count(Recipe.id))
        .where(Recipe.owner_user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    plan_count_subq = (
        select(func.count(Plan.id))
        .where(Plan.owner_user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )

    stmt = select(
        User,
        profile_count_subq.label("profiles_count"),
        recipe_count_subq.label("recipes_count"),
        plan_count_subq.label("plans_count"),
    ).order_by(User.created_at.desc(), User.id.desc())

    if q_normalized:
        like_pattern = f"%{q_normalized.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(User.email).like(like_pattern),
                func.lower(User.username).like(like_pattern),
                func.lower(func.coalesce(User.display_name, "")).like(like_pattern),
            )
        )

    stmt = stmt.limit(limit).offset(offset)
    rows = db.execute(stmt).all()

    result: list[dict] = []
    for row in rows:
        user = row[0]
        result.append(
            {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "display_name": user.display_name,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": user.created_at,
                "profiles_count": int(row.profiles_count or 0),
                "recipes_count": int(row.recipes_count or 0),
                "plans_count": int(row.plans_count or 0),
            }
        )
    return result


def apply_resolution_side_effects_for_food(
    db: Session,
    *,
    food_id: int,
    resolution: str,
) -> None:
    if resolution == "content_hidden":
        food = db.execute(select(FoodItem).where(FoodItem.id == food_id)).scalar_one_or_none()
        if food is not None:
            food.is_listed = False
    elif resolution == "content_restored":
        food = db.execute(select(FoodItem).where(FoodItem.id == food_id)).scalar_one_or_none()
        if food is not None and food.source in {FoodSource.community, FoodSource.verified}:
            food.status = FoodStatus.approved
            food.is_listed = True
    elif resolution == "content_rejected":
        food = db.execute(select(FoodItem).where(FoodItem.id == food_id)).scalar_one_or_none()
        if food is not None and food.source in {FoodSource.community, FoodSource.verified}:
            food.status = FoodStatus.rejected
            food.is_listed = False
    elif resolution != "no_action":
        raise AdminReportResolutionError("Invalid resolution")

    db.commit()


def apply_resolution_side_effects_for_recipe(
    db: Session,
    *,
    recipe_id: int,
    resolution: str,
) -> None:
    if resolution == "content_hidden":
        recipe = db.execute(select(Recipe).where(Recipe.id == recipe_id)).scalar_one_or_none()
        if recipe is not None:
            recipe.is_listed = False
    elif resolution == "content_restored":
        recipe = db.execute(select(Recipe).where(Recipe.id == recipe_id)).scalar_one_or_none()
        if recipe is not None and recipe.source == FoodSource.community:
            recipe.status = FoodStatus.approved
            recipe.is_listed = True
    elif resolution == "content_rejected":
        recipe = db.execute(select(Recipe).where(Recipe.id == recipe_id)).scalar_one_or_none()
        if recipe is not None and recipe.source == FoodSource.community:
            recipe.status = FoodStatus.rejected
            recipe.is_listed = False
    elif resolution != "no_action":
        raise AdminReportResolutionError("Invalid resolution")

    db.commit()
