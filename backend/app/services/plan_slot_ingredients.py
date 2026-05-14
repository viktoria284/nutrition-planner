from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import FoodSource, FoodStatus
from app.models.foods import FoodItem
from app.models.plan import Plan
from app.models.plan_slot import PlanSlot, PlanSlotIngredientOverride
from app.models.recipe import Recipe, RecipeIngredient
from app.schemas.plan import (
    PlanSlotEffectiveIngredientRead,
    PlanSlotEffectiveIngredientsResponse,
    PlanSlotIngredientOverridesReplaceRequest,
)

NUTRIENT_QUANT = Decimal("0.01")
HUNDRED_GRAMS = Decimal("100")


class PlanSlotIngredientsPlanNotFoundError(ValueError):
    pass


class PlanSlotIngredientsSlotNotFoundError(ValueError):
    pass


class PlanSlotIngredientsRecipeRequiredError(ValueError):
    pass


class PlanSlotIngredientsRecipeIngredientInvalidError(ValueError):
    pass


class PlanSlotIngredientsFoodNotFoundError(ValueError):
    pass


def _quantize_nutrient(value: Decimal) -> Decimal:
    return value.quantize(NUTRIENT_QUANT, rounding=ROUND_HALF_UP)


def _base_slot_ingredient_grams(*, ingredient_grams: Decimal, recipe_servings_count: int, slot_multiplier: Decimal) -> Decimal:
    if recipe_servings_count <= 0:
        return Decimal("0")
    per_serving = ingredient_grams / Decimal(recipe_servings_count)
    return _quantize_nutrient(per_serving * slot_multiplier)


def _build_effective_item_payload(
    *,
    recipe_ingredient_id: int | None,
    override_id: int | None,
    source: str,
    food: FoodItem,
    grams: Decimal,
) -> dict[str, object]:
    grams_value = _quantize_nutrient(grams)
    factor = grams_value / HUNDRED_GRAMS
    return {
        "recipe_ingredient_id": recipe_ingredient_id,
        "override_id": override_id,
        "source": source,
        "food_id": food.id,
        "food_name": food.name,
        "grams": grams_value,
        "kcal": _quantize_nutrient(food.kcal * factor),
        "protein": _quantize_nutrient(food.protein * factor),
        "fat": _quantize_nutrient(food.fat * factor),
        "carbs": _quantize_nutrient(food.carbs * factor),
        "fiber": _quantize_nutrient(food.fiber * factor),
    }


def _get_plan_or_404(db: Session, user_id: int, plan_id: int) -> Plan:
    plan = db.execute(
        select(Plan).where(
            Plan.id == plan_id,
            Plan.owner_user_id == user_id,
        )
    ).scalar_one_or_none()
    if plan is None:
        raise PlanSlotIngredientsPlanNotFoundError("Plan not found")
    return plan


def _get_slot_or_404(
    db: Session,
    *,
    plan_id: int,
    slot_id: int,
    with_relations: bool,
) -> PlanSlot:
    stmt = select(PlanSlot).where(
        PlanSlot.id == slot_id,
        PlanSlot.plan_id == plan_id,
    )
    if with_relations:
        stmt = stmt.options(
            selectinload(PlanSlot.recipe)
            .selectinload(Recipe.ingredients)
            .selectinload(RecipeIngredient.food),
            selectinload(PlanSlot.ingredient_overrides).selectinload(PlanSlotIngredientOverride.food),
            selectinload(PlanSlot.ingredient_overrides).selectinload(PlanSlotIngredientOverride.recipe_ingredient),
        )

    slot = db.execute(stmt).scalar_one_or_none()
    if slot is None:
        raise PlanSlotIngredientsSlotNotFoundError("Plan slot not found")
    return slot


def _get_accessible_food_for_override(db: Session, *, user_id: int, food_id: int) -> FoodItem | None:
    return db.execute(
        select(FoodItem).where(
            FoodItem.id == food_id,
            or_(
                and_(FoodItem.source == FoodSource.private, FoodItem.owner_user_id == user_id),
                FoodItem.source == FoodSource.verified,
                and_(
                    FoodItem.source == FoodSource.community,
                    FoodItem.status == FoodStatus.approved,
                    FoodItem.is_listed.is_(True),
                ),
            ),
        )
    ).scalar_one_or_none()


def build_slot_effective_items(slot: PlanSlot) -> list[dict[str, object]]:
    if slot.recipe_id is None or slot.recipe is None:
        return []

    recipe_ingredients = sorted(slot.recipe.ingredients, key=lambda ingredient: (ingredient.id, ingredient.created_at))
    overrides = list(slot.ingredient_overrides)

    override_by_recipe_ingredient_id: dict[int, PlanSlotIngredientOverride] = {}
    manual_overrides: list[PlanSlotIngredientOverride] = []

    for override in overrides:
        if override.is_manual:
            manual_overrides.append(override)
            continue
        if override.recipe_ingredient_id is None:
            continue
        override_by_recipe_ingredient_id[override.recipe_ingredient_id] = override

    effective_items: list[dict[str, object]] = []

    for ingredient in recipe_ingredients:
        if ingredient.food is None:
            continue
        base_grams = _base_slot_ingredient_grams(
            ingredient_grams=ingredient.grams,
            recipe_servings_count=slot.recipe.servings_count,
            slot_multiplier=slot.servings_multiplier,
        )
        override = override_by_recipe_ingredient_id.get(ingredient.id)
        if override is not None and override.is_excluded:
            continue

        resolved_food = ingredient.food
        resolved_grams = base_grams
        source = "base"
        override_id: int | None = None

        if override is not None:
            override_id = override.id
            source = "overridden"
            if override.food is not None:
                resolved_food = override.food
            if override.grams is not None:
                resolved_grams = override.grams

        effective_items.append(
            _build_effective_item_payload(
                recipe_ingredient_id=ingredient.id,
                override_id=override_id,
                source=source,
                food=resolved_food,
                grams=resolved_grams,
            )
        )

    for manual in sorted(manual_overrides, key=lambda value: (value.created_at, value.id)):
        if manual.food is None or manual.grams is None:
            continue
        effective_items.append(
            _build_effective_item_payload(
                recipe_ingredient_id=None,
                override_id=manual.id,
                source="manual",
                food=manual.food,
                grams=manual.grams,
            )
        )

    return effective_items


def calculate_effective_items_totals(items: list[dict[str, object]]) -> dict[str, Decimal]:
    totals = {
        "kcal": Decimal("0"),
        "protein": Decimal("0"),
        "fat": Decimal("0"),
        "carbs": Decimal("0"),
        "fiber": Decimal("0"),
    }
    for item in items:
        totals["kcal"] += Decimal(item["kcal"])
        totals["protein"] += Decimal(item["protein"])
        totals["fat"] += Decimal(item["fat"])
        totals["carbs"] += Decimal(item["carbs"])
        totals["fiber"] += Decimal(item["fiber"])

    return {key: _quantize_nutrient(value) for key, value in totals.items()}


def build_effective_ingredients_response(slot: PlanSlot) -> PlanSlotEffectiveIngredientsResponse:
    if slot.recipe_id is None:
        raise PlanSlotIngredientsRecipeRequiredError("Сначала выберите рецепт для слота.")

    items = build_slot_effective_items(slot)
    excluded_recipe_ingredient_ids = sorted(
        [
            int(override.recipe_ingredient_id)
            for override in slot.ingredient_overrides
            if override.is_excluded and override.recipe_ingredient_id is not None
        ]
    )
    return PlanSlotEffectiveIngredientsResponse.model_validate(
        {
            "slot_id": slot.id,
            "recipe_id": slot.recipe_id,
            "has_overrides": len(slot.ingredient_overrides) > 0,
            "excluded_recipe_ingredient_ids": excluded_recipe_ingredient_ids,
            "items": [PlanSlotEffectiveIngredientRead.model_validate(item) for item in items],
        }
    )


def get_slot_effective_ingredients(
    db: Session,
    *,
    user_id: int,
    plan_id: int,
    slot_id: int,
) -> PlanSlotEffectiveIngredientsResponse:
    plan = _get_plan_or_404(db, user_id, plan_id)
    slot = _get_slot_or_404(db, plan_id=plan.id, slot_id=slot_id, with_relations=True)
    return build_effective_ingredients_response(slot)


def clear_slot_ingredient_overrides(db: Session, *, slot_id: int) -> None:
    db.execute(delete(PlanSlotIngredientOverride).where(PlanSlotIngredientOverride.slot_id == slot_id))


def replace_slot_ingredient_overrides(
    db: Session,
    *,
    user_id: int,
    plan_id: int,
    slot_id: int,
    payload: PlanSlotIngredientOverridesReplaceRequest,
) -> PlanSlotEffectiveIngredientsResponse:
    plan = _get_plan_or_404(db, user_id, plan_id)
    slot = _get_slot_or_404(db, plan_id=plan.id, slot_id=slot_id, with_relations=True)

    if slot.recipe_id is None or slot.recipe is None:
        raise PlanSlotIngredientsRecipeRequiredError("Сначала выберите рецепт для слота.")

    recipe_ingredient_by_id = {ingredient.id: ingredient for ingredient in slot.recipe.ingredients}

    clear_slot_ingredient_overrides(db, slot_id=slot.id)

    new_overrides: list[PlanSlotIngredientOverride] = []

    for item in payload.base_overrides:
        ingredient = recipe_ingredient_by_id.get(item.recipe_ingredient_id)
        if ingredient is None:
            raise PlanSlotIngredientsRecipeIngredientInvalidError("Ингредиент рецепта не найден для этого слота.")

        override_food_id = item.food_id
        if override_food_id is not None:
            accessible_food = _get_accessible_food_for_override(db, user_id=user_id, food_id=override_food_id)
            if accessible_food is None:
                raise PlanSlotIngredientsFoodNotFoundError("Продукт не найден или недоступен.")

        new_overrides.append(
            PlanSlotIngredientOverride(
                slot_id=slot.id,
                recipe_ingredient_id=ingredient.id,
                food_id=override_food_id,
                grams=item.grams if not item.is_excluded else None,
                is_excluded=item.is_excluded,
                is_manual=False,
            )
        )

    for manual_item in payload.manual_items:
        accessible_food = _get_accessible_food_for_override(db, user_id=user_id, food_id=manual_item.food_id)
        if accessible_food is None:
            raise PlanSlotIngredientsFoodNotFoundError("Продукт не найден или недоступен.")

        new_overrides.append(
            PlanSlotIngredientOverride(
                slot_id=slot.id,
                recipe_ingredient_id=None,
                food_id=manual_item.food_id,
                grams=manual_item.grams,
                is_excluded=False,
                is_manual=True,
            )
        )

    if new_overrides:
        db.add_all(new_overrides)

    db.commit()

    refreshed_slot = _get_slot_or_404(db, plan_id=plan.id, slot_id=slot.id, with_relations=True)
    return build_effective_ingredients_response(refreshed_slot)


def delete_slot_ingredient_overrides(
    db: Session,
    *,
    user_id: int,
    plan_id: int,
    slot_id: int,
) -> PlanSlotEffectiveIngredientsResponse:
    plan = _get_plan_or_404(db, user_id, plan_id)
    slot = _get_slot_or_404(db, plan_id=plan.id, slot_id=slot_id, with_relations=True)
    if slot.recipe_id is None or slot.recipe is None:
        raise PlanSlotIngredientsRecipeRequiredError("Сначала выберите рецепт для слота.")

    clear_slot_ingredient_overrides(db, slot_id=slot.id)
    db.commit()

    refreshed_slot = _get_slot_or_404(db, plan_id=plan.id, slot_id=slot.id, with_relations=True)
    return build_effective_ingredients_response(refreshed_slot)
