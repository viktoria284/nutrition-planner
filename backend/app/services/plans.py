from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.plan import Plan
from app.models.plan_slot import PlanSlot
from app.models.recipe import Recipe, RecipeIngredient
from app.schemas.plan import (
    NutritionTotalsRead,
    PlanCreate,
    PlanDayRead,
    PlanListItem,
    PlanRead,
    PlanSlotRead,
    PlanSlotUpdate,
)
from app.services.recipes import calculate_recipe_nutrients, get_accessible_recipe_by_id


class PlanNotFoundError(ValueError):
    pass


class PlanSlotNotFoundError(ValueError):
    pass


class PlanSlotRecipeNotFoundError(ValueError):
    pass


NUTRIENT_QUANT = Decimal("0.01")


def _quantize_nutrient(value: Decimal) -> Decimal:
    return value.quantize(NUTRIENT_QUANT, rounding=ROUND_HALF_UP)


def _zero_nutrition_totals() -> dict[str, Decimal]:
    return {
        "kcal": Decimal("0"),
        "protein": Decimal("0"),
        "fat": Decimal("0"),
        "carbs": Decimal("0"),
    }


def _sort_slots(slots: list[PlanSlot]) -> list[PlanSlot]:
    return sorted(
        slots,
        key=lambda slot: (slot.day_date, slot.slot_index, slot.id),
    )


def _build_slot_payload(
    slot: PlanSlot,
    *,
    recipe_per_serving_cache: dict[int, dict[str, Decimal]],
) -> dict:
    totals = _zero_nutrition_totals()
    if slot.recipe_id is not None:
        recipe_totals = recipe_per_serving_cache.get(slot.recipe_id)
        if recipe_totals:
            totals["kcal"] = recipe_totals["kcal"] * slot.servings_multiplier
            totals["protein"] = recipe_totals["protein"] * slot.servings_multiplier
            totals["fat"] = recipe_totals["fat"] * slot.servings_multiplier
            totals["carbs"] = recipe_totals["carbs"] * slot.servings_multiplier

    return {
        "id": slot.id,
        "plan_id": slot.plan_id,
        "day_date": slot.day_date,
        "slot_index": slot.slot_index,
        "recipe_id": slot.recipe_id,
        "servings_multiplier": slot.servings_multiplier,
        "slot_kcal": _quantize_nutrient(totals["kcal"]),
        "slot_protein": _quantize_nutrient(totals["protein"]),
        "slot_fat": _quantize_nutrient(totals["fat"]),
        "slot_carbs": _quantize_nutrient(totals["carbs"]),
        "pinned": slot.pinned,
        "created_at": slot.created_at,
        "updated_at": slot.updated_at,
    }


def _get_plan_or_404(db: Session, user_id: int, plan_id: int, *, with_slots: bool = False) -> Plan:
    stmt = select(Plan).where(
        Plan.id == plan_id,
        Plan.owner_user_id == user_id,
    )
    if with_slots:
        stmt = stmt.options(
            selectinload(Plan.profile),
            selectinload(Plan.slots)
            .selectinload(PlanSlot.recipe)
            .selectinload(Recipe.ingredients)
            .selectinload(RecipeIngredient.food)
        )

    plan = db.execute(stmt).scalar_one_or_none()
    if not plan:
        raise PlanNotFoundError("Plan not found")
    return plan


def build_plan_read(plan: Plan) -> PlanRead:
    sorted_slots = _sort_slots(list(plan.slots))
    day_buckets: dict = defaultdict(list)
    for slot in sorted_slots:
        day_buckets[slot.day_date].append(slot)

    recipe_per_serving_cache: dict[int, dict[str, Decimal]] = {}
    for slot in sorted_slots:
        if slot.recipe_id is None or slot.recipe is None:
            continue
        if slot.recipe_id in recipe_per_serving_cache:
            continue
        nutrients = calculate_recipe_nutrients(slot.recipe)
        recipe_per_serving_cache[slot.recipe_id] = {
            "kcal": nutrients["per_serving_kcal"],
            "protein": nutrients["per_serving_protein"],
            "fat": nutrients["per_serving_fat"],
            "carbs": nutrients["per_serving_carbs"],
        }

    slot_payload_by_id = {
        slot.id: _build_slot_payload(slot, recipe_per_serving_cache=recipe_per_serving_cache)
        for slot in sorted_slots
    }

    days_payload: list[PlanDayRead] = []
    for day_date in sorted(day_buckets):
        day_slots = _sort_slots(day_buckets[day_date])
        totals = _zero_nutrition_totals()
        for slot in day_slots:
            if slot.recipe_id is None:
                continue
            recipe_totals = recipe_per_serving_cache.get(slot.recipe_id)
            if not recipe_totals:
                continue
            totals["kcal"] += recipe_totals["kcal"] * slot.servings_multiplier
            totals["protein"] += recipe_totals["protein"] * slot.servings_multiplier
            totals["fat"] += recipe_totals["fat"] * slot.servings_multiplier
            totals["carbs"] += recipe_totals["carbs"] * slot.servings_multiplier

        days_payload.append(
            PlanDayRead.model_validate(
                {
                    "date": day_date,
                    "totals": NutritionTotalsRead.model_validate(
                        {
                            "kcal": _quantize_nutrient(totals["kcal"]),
                            "protein": _quantize_nutrient(totals["protein"]),
                            "fat": _quantize_nutrient(totals["fat"]),
                            "carbs": _quantize_nutrient(totals["carbs"]),
                        }
                    ),
                    "slots": [PlanSlotRead.model_validate(slot_payload_by_id[slot.id]) for slot in day_slots],
                }
            )
        )

    return PlanRead.model_validate(
        {
            "id": plan.id,
            "owner_user_id": plan.owner_user_id,
            "profile_id": plan.profile_id,
            "profile_name": plan.profile.name if plan.profile is not None else None,
            "start_date": plan.start_date,
            "days_count": plan.days_count,
            "meals_per_day": plan.meals_per_day,
            "title": plan.title,
            "target_kcal": plan.target_kcal,
            "target_protein": plan.target_protein,
            "target_fat": plan.target_fat,
            "target_carbs": plan.target_carbs,
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
            "slots": [PlanSlotRead.model_validate(slot_payload_by_id[slot.id]) for slot in sorted_slots],
            "days": days_payload,
        }
    )


def build_plan_slot_read(slot: PlanSlot) -> PlanSlotRead:
    recipe_per_serving_cache: dict[int, dict[str, Decimal]] = {}
    if slot.recipe_id is not None and slot.recipe is not None:
        nutrients = calculate_recipe_nutrients(slot.recipe)
        recipe_per_serving_cache[slot.recipe_id] = {
            "kcal": nutrients["per_serving_kcal"],
            "protein": nutrients["per_serving_protein"],
            "fat": nutrients["per_serving_fat"],
            "carbs": nutrients["per_serving_carbs"],
        }
    return PlanSlotRead.model_validate(
        _build_slot_payload(slot, recipe_per_serving_cache=recipe_per_serving_cache)
    )


def list_plans_for_user(db: Session, user_id: int) -> list[Plan]:
    return db.execute(
        select(Plan)
        .options(selectinload(Plan.profile))
        .where(Plan.owner_user_id == user_id)
        .order_by(Plan.updated_at.desc(), Plan.id.desc())
    ).scalars().all()


def build_plan_list_item(plan: Plan) -> PlanListItem:
    return PlanListItem.model_validate(
        {
            "id": plan.id,
            "owner_user_id": plan.owner_user_id,
            "profile_id": plan.profile_id,
            "profile_name": plan.profile.name if plan.profile is not None else None,
            "start_date": plan.start_date,
            "days_count": plan.days_count,
            "meals_per_day": plan.meals_per_day,
            "title": plan.title,
            "target_kcal": plan.target_kcal,
            "target_protein": plan.target_protein,
            "target_fat": plan.target_fat,
            "target_carbs": plan.target_carbs,
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
        }
    )


def create_plan(db: Session, user_id: int, payload: PlanCreate) -> Plan:
    plan = Plan(
        owner_user_id=user_id,
        start_date=payload.start_date,
        days_count=payload.days_count,
        meals_per_day=payload.meals_per_day,
        title=payload.title,
    )
    db.add(plan)
    db.flush()

    slots: list[PlanSlot] = []
    for day_offset in range(payload.days_count):
        day_date = payload.start_date + timedelta(days=day_offset)
        for slot_index in range(payload.meals_per_day):
            slots.append(
                PlanSlot(
                    plan_id=plan.id,
                    day_date=day_date,
                    slot_index=slot_index,
                    recipe_id=None,
                    servings_multiplier=Decimal("1"),
                    pinned=False,
                )
            )

    db.add_all(slots)
    db.commit()

    return _get_plan_or_404(db, user_id, plan.id, with_slots=True)


def get_plan_for_user(db: Session, user_id: int, plan_id: int) -> Plan:
    return _get_plan_or_404(db, user_id, plan_id, with_slots=True)


def delete_plan_for_user(db: Session, user_id: int, plan_id: int) -> None:
    plan = _get_plan_or_404(db, user_id, plan_id, with_slots=False)
    db.delete(plan)
    db.commit()


def update_plan_slot(
    db: Session,
    user_id: int,
    plan_id: int,
    slot_id: int,
    payload: PlanSlotUpdate,
) -> PlanSlot:
    plan = _get_plan_or_404(db, user_id, plan_id, with_slots=False)
    slot = db.execute(
        select(PlanSlot).where(
            PlanSlot.id == slot_id,
            PlanSlot.plan_id == plan.id,
        )
    ).scalar_one_or_none()
    if not slot:
        raise PlanSlotNotFoundError("Plan slot not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "recipe_id" in update_data:
        recipe_id = update_data["recipe_id"]
        if recipe_id is None:
            slot.recipe_id = None
        else:
            recipe = get_accessible_recipe_by_id(db, user_id, recipe_id)
            if not recipe:
                raise PlanSlotRecipeNotFoundError("Recipe not found")
            slot.recipe_id = recipe.id

    if "servings_multiplier" in update_data:
        slot.servings_multiplier = update_data["servings_multiplier"]

    if "pinned" in update_data:
        slot.pinned = update_data["pinned"]

    db.commit()
    refreshed_slot = db.execute(
        select(PlanSlot)
        .where(PlanSlot.id == slot.id)
        .options(
            selectinload(PlanSlot.recipe)
            .selectinload(Recipe.ingredients)
            .selectinload(RecipeIngredient.food)
        )
    ).scalar_one()
    return refreshed_slot
