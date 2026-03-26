from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.plan import Plan
from app.models.plan_slot import PlanSlot
from app.models.recipe import Recipe, RecipeIngredient
from app.models.shopping import ShoppingManualItem, ShoppingOverride
from app.schemas.shopping import (
    ShoppingListItemRead,
    ShoppingListRead,
    ShoppingManualItemCreate,
    ShoppingManualItemRead,
    ShoppingOverrideUpdate,
)


class ShoppingPlanNotFoundError(ValueError):
    pass


class ShoppingFoodNotFoundError(ValueError):
    pass


class ShoppingManualItemNotFoundError(ValueError):
    pass


GRAMS_QUANT = Decimal("0.01")


def _quantize_grams(value: Decimal) -> Decimal:
    return value.quantize(GRAMS_QUANT, rounding=ROUND_HALF_UP)


def _get_plan_or_404(
    db: Session,
    user_id: int,
    plan_id: int,
    *,
    with_slots: bool = False,
) -> Plan:
    stmt = select(Plan).where(
        Plan.id == plan_id,
        Plan.owner_user_id == user_id,
    )
    if with_slots:
        stmt = stmt.options(
            selectinload(Plan.slots)
            .selectinload(PlanSlot.recipe)
            .selectinload(Recipe.ingredients)
            .selectinload(RecipeIngredient.food)
        )
    plan = db.execute(stmt).scalar_one_or_none()
    if not plan:
        raise ShoppingPlanNotFoundError("Plan not found")
    return plan


def _build_computed_food_totals(plan: Plan) -> dict[int, dict[str, object]]:
    grouped: dict[int, dict[str, object]] = {}
    for slot in plan.slots:
        if slot.recipe_id is None or slot.recipe is None:
            continue
        for ingredient in slot.recipe.ingredients:
            if ingredient.food is None:
                continue
            bucket = grouped.get(ingredient.food_id)
            if bucket is None:
                bucket = {
                    "food_id": ingredient.food_id,
                    "name": ingredient.food.name,
                    "brand": ingredient.food.brand,
                    "total_grams": Decimal("0"),
                }
                grouped[ingredient.food_id] = bucket
            bucket["total_grams"] = bucket["total_grams"] + (ingredient.grams * slot.servings_multiplier)
    return grouped


def _build_shopping_list_read(
    *,
    plan: Plan,
    overrides: list[ShoppingOverride],
    manual_items: list[ShoppingManualItem],
) -> ShoppingListRead:
    computed_by_food = _build_computed_food_totals(plan)
    overrides_by_food = {override.food_id: override for override in overrides}

    computed_payload: list[ShoppingListItemRead] = []
    computed_values = sorted(
        computed_by_food.values(),
        key=lambda item: (str(item["name"]).lower(), int(item["food_id"])),
    )
    for item in computed_values:
        override = overrides_by_food.get(int(item["food_id"]))
        total_grams = _quantize_grams(item["total_grams"])
        adjusted_grams = None
        checked = False
        excluded = False
        if override is not None:
            checked = override.checked
            excluded = override.excluded
            if override.adjusted_grams is not None:
                adjusted_grams = _quantize_grams(override.adjusted_grams)

        if excluded:
            continue

        effective_grams = adjusted_grams if adjusted_grams is not None else total_grams
        computed_payload.append(
            ShoppingListItemRead.model_validate(
                {
                    "food_id": item["food_id"],
                    "name": item["name"],
                    "brand": item["brand"],
                    "total_grams": total_grams,
                    "checked": checked,
                    "excluded": excluded,
                    "adjusted_grams": adjusted_grams,
                    "effective_grams": effective_grams,
                    "is_manual": False,
                }
            )
        )

    manual_payload = [
        ShoppingManualItemRead.model_validate(item)
        for item in sorted(
            manual_items,
            key=lambda manual: (manual.created_at, manual.id),
        )
    ]
    return ShoppingListRead.model_validate({"items": [*computed_payload, *manual_payload]})


def get_plan_shopping_list(db: Session, user_id: int, plan_id: int) -> ShoppingListRead:
    plan = _get_plan_or_404(db, user_id, plan_id, with_slots=True)
    overrides = db.execute(
        select(ShoppingOverride).where(ShoppingOverride.plan_id == plan.id)
    ).scalars().all()
    manual_items = db.execute(
        select(ShoppingManualItem).where(ShoppingManualItem.plan_id == plan.id)
    ).scalars().all()
    return _build_shopping_list_read(plan=plan, overrides=overrides, manual_items=manual_items)


def update_shopping_override(
    db: Session,
    user_id: int,
    plan_id: int,
    food_id: int,
    payload: ShoppingOverrideUpdate,
) -> ShoppingListItemRead:
    plan = _get_plan_or_404(db, user_id, plan_id, with_slots=True)
    computed_by_food = _build_computed_food_totals(plan)
    computed_food = computed_by_food.get(food_id)
    if not computed_food:
        raise ShoppingFoodNotFoundError("Food not found in shopping list")

    override = db.execute(
        select(ShoppingOverride).where(
            ShoppingOverride.plan_id == plan.id,
            ShoppingOverride.food_id == food_id,
        )
    ).scalar_one_or_none()
    if override is None:
        override = ShoppingOverride(
            plan_id=plan.id,
            food_id=food_id,
            checked=False,
            excluded=False,
            adjusted_grams=None,
        )
        db.add(override)

    update_data = payload.model_dump(exclude_unset=True)
    if "checked" in update_data:
        override.checked = update_data["checked"]
    if "excluded" in update_data:
        override.excluded = update_data["excluded"]
    if "adjusted_grams" in update_data:
        override.adjusted_grams = update_data["adjusted_grams"]

    db.commit()
    db.refresh(override)

    total_grams = _quantize_grams(computed_food["total_grams"])
    adjusted_grams = _quantize_grams(override.adjusted_grams) if override.adjusted_grams is not None else None
    effective_grams = adjusted_grams if adjusted_grams is not None else total_grams
    return ShoppingListItemRead.model_validate(
        {
            "food_id": computed_food["food_id"],
            "name": computed_food["name"],
            "brand": computed_food["brand"],
            "total_grams": total_grams,
            "checked": override.checked,
            "excluded": override.excluded,
            "adjusted_grams": adjusted_grams,
            "effective_grams": effective_grams,
            "is_manual": False,
        }
    )


def create_manual_shopping_item(
    db: Session,
    user_id: int,
    plan_id: int,
    payload: ShoppingManualItemCreate,
) -> ShoppingManualItem:
    plan = _get_plan_or_404(db, user_id, plan_id, with_slots=False)
    manual_item = ShoppingManualItem(
        plan_id=plan.id,
        name=payload.name,
        grams=payload.grams,
        unit=payload.unit,
        checked=False,
    )
    db.add(manual_item)
    db.commit()
    db.refresh(manual_item)
    return manual_item


def delete_manual_shopping_item(
    db: Session,
    user_id: int,
    plan_id: int,
    manual_item_id: int,
) -> None:
    plan = _get_plan_or_404(db, user_id, plan_id, with_slots=False)
    manual_item = db.execute(
        select(ShoppingManualItem).where(
            ShoppingManualItem.id == manual_item_id,
            ShoppingManualItem.plan_id == plan.id,
        )
    ).scalar_one_or_none()
    if manual_item is None:
        raise ShoppingManualItemNotFoundError("Manual shopping item not found")

    db.delete(manual_item)
    db.commit()
