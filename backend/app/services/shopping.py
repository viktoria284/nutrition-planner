from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.constants import DEFAULT_FOOD_CATEGORY
from app.models.foods import FoodItem
from app.models.plan import Plan
from app.models.plan_slot import PlanSlot, PlanSlotIngredientOverride
from app.models.recipe import Recipe, RecipeIngredient
from app.models.shopping import ShoppingList, ShoppingListItem, ShoppingListSource
from app.schemas.shopping import (
    ShoppingListBulkDeleteRequest,
    ShoppingListBulkDeleteResponse,
    ShoppingListCreateFromPlanRequest,
    ShoppingListItemRead,
    ShoppingListItemUpdate,
    ShoppingListMergeRequest,
    ShoppingListRead,
    ShoppingListSummaryRead,
    ShoppingManualItemCreate,
)
from app.services.plan_slot_ingredients import build_slot_effective_items


class ShoppingPlanNotFoundError(ValueError):
    pass


class ShoppingListNotFoundError(ValueError):
    pass


class ShoppingListItemNotFoundError(ValueError):
    pass


class ShoppingItemUpdateForbiddenError(ValueError):
    pass


class ShoppingListSourceNotSupportedError(ValueError):
    pass


GRAMS_QUANT = Decimal("0.01")


def _quantize_grams(value: Decimal) -> Decimal:
    return value.quantize(GRAMS_QUANT, rounding=ROUND_HALF_UP)


def _build_plan_default_title(plan: Plan) -> str:
    if plan.title:
        return f"Список покупок: {plan.title}"
    end_date = plan.start_date
    if plan.days_count > 1:
        end_date = plan.start_date.fromordinal(plan.start_date.toordinal() + plan.days_count - 1)
    return f"Список покупок: {plan.start_date.isoformat()} - {end_date.isoformat()}"


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
            .selectinload(RecipeIngredient.food),
            selectinload(Plan.slots)
            .selectinload(PlanSlot.ingredient_overrides)
            .selectinload(PlanSlotIngredientOverride.food),
        )
    plan = db.execute(stmt).scalar_one_or_none()
    if plan is None:
        raise ShoppingPlanNotFoundError("Plan not found")
    return plan


def _build_computed_food_totals(plan: Plan) -> dict[int, dict[str, object]]:
    grouped: dict[int, dict[str, object]] = {}
    for slot in plan.slots:
        if slot.recipe_id is None or slot.recipe is None:
            continue

        for effective_item in build_slot_effective_items(slot):
            food_id = int(effective_item["food_id"])
            bucket = grouped.get(food_id)
            if bucket is None:
                bucket = {
                    "food_id": food_id,
                    "name_snapshot": str(effective_item["food_name"]),
                    "category": DEFAULT_FOOD_CATEGORY,
                    "planned_grams": Decimal("0"),
                }
                grouped[food_id] = bucket

            bucket["planned_grams"] = bucket["planned_grams"] + Decimal(effective_item["grams"])

        # Update categories from loaded foods for more stable grouping labels.
        for ingredient in slot.recipe.ingredients:
            if ingredient.food is None:
                continue
            if ingredient.food_id in grouped:
                grouped[ingredient.food_id]["category"] = ingredient.food.category or DEFAULT_FOOD_CATEGORY
        for override in slot.ingredient_overrides:
            if override.food is None:
                continue
            if override.food_id in grouped:
                grouped[override.food_id]["category"] = override.food.category or DEFAULT_FOOD_CATEGORY
    return grouped


def _compute_plan_source_signature(plan: Plan) -> str:
    slot_payload = []
    for slot in sorted(plan.slots, key=lambda value: (value.id, value.day_date, value.slot_index)):
        overrides_payload = []
        for override in sorted(
            slot.ingredient_overrides,
            key=lambda value: (value.is_manual, value.recipe_ingredient_id or 0, value.food_id or 0, value.id),
        ):
            overrides_payload.append(
                {
                    "recipe_ingredient_id": override.recipe_ingredient_id,
                    "food_id": override.food_id,
                    "grams": str(override.grams) if override.grams is not None else None,
                    "is_excluded": override.is_excluded,
                    "is_manual": override.is_manual,
                    "updated_at": override.updated_at.isoformat() if override.updated_at is not None else None,
                }
            )
        slot_payload.append(
            {
                "slot_id": slot.id,
                "recipe_id": slot.recipe_id,
                "servings_multiplier": str(slot.servings_multiplier),
                "updated_at": slot.updated_at.isoformat() if slot.updated_at is not None else None,
                "ingredient_overrides": overrides_payload,
            }
        )
    raw = json.dumps(slot_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _compute_plan_sources_signature(db: Session, user_id: int, plan_ids: list[int]) -> str | None:
    unique_plan_ids = sorted(set(plan_ids))
    if not unique_plan_ids:
        return None

    plan_signatures = []
    for plan_id in unique_plan_ids:
        plan = _get_plan_or_404(db, user_id, plan_id, with_slots=True)
        plan_signatures.append(
            {
                "plan_id": plan.id,
                "signature": _compute_plan_source_signature(plan),
            }
        )

    if len(plan_signatures) == 1:
        return str(plan_signatures[0]["signature"])

    raw = json.dumps(plan_signatures, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_shopping_list_or_404(
    db: Session,
    user_id: int,
    shopping_list_id: int,
    *,
    with_relations: bool = False,
) -> ShoppingList:
    stmt = select(ShoppingList).where(
        ShoppingList.id == shopping_list_id,
        ShoppingList.owner_user_id == user_id,
    )
    if with_relations:
        stmt = stmt.options(
            selectinload(ShoppingList.sources),
            selectinload(ShoppingList.items),
        )
    shopping_list = db.execute(stmt).scalar_one_or_none()
    if shopping_list is None:
        raise ShoppingListNotFoundError("Shopping list not found")
    return shopping_list


def _build_item_read(item: ShoppingListItem) -> ShoppingListItemRead:
    effective_grams = item.adjusted_grams if item.adjusted_grams is not None else item.planned_grams
    return ShoppingListItemRead.model_validate(
        {
            "id": item.id,
            "shopping_list_id": item.shopping_list_id,
            "food_id": item.food_id,
            "name_snapshot": item.name_snapshot,
            "category": item.category,
            "item_type": item.item_type,
            "planned_grams": _quantize_grams(item.planned_grams) if item.planned_grams is not None else None,
            "adjusted_grams": _quantize_grams(item.adjusted_grams) if item.adjusted_grams is not None else None,
            "effective_grams": _quantize_grams(effective_grams) if effective_grams is not None else None,
            "unit": item.unit,
            "checked": item.checked,
            "excluded": item.excluded,
            "sort_order": item.sort_order,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
    )


def _build_computed_food_totals_for_plans(plans: list[Plan]) -> dict[int, dict[str, object]]:
    grouped: dict[int, dict[str, object]] = {}
    for plan in plans:
        plan_totals = _build_computed_food_totals(plan)
        for food_id, item in plan_totals.items():
            bucket = grouped.get(food_id)
            if bucket is None:
                grouped[food_id] = dict(item)
                continue
            bucket["planned_grams"] = bucket["planned_grams"] + item["planned_grams"]
            bucket["name_snapshot"] = item["name_snapshot"]
            bucket["category"] = item["category"]
    return grouped


def _build_shopping_list_read(
    shopping_list: ShoppingList,
    *,
    is_outdated: bool,
) -> ShoppingListRead:
    sorted_items = sorted(
        shopping_list.items,
        key=lambda item: (item.sort_order, item.created_at, item.id),
    )
    sources = sorted(shopping_list.sources, key=lambda source: (source.created_at, source.id))
    return ShoppingListRead.model_validate(
        {
            "id": shopping_list.id,
            "owner_user_id": shopping_list.owner_user_id,
            "title": shopping_list.title,
            "status": shopping_list.status,
            "source_type": shopping_list.source_type,
            "source_signature": shopping_list.source_signature,
            "is_outdated": is_outdated,
            "generated_at": shopping_list.generated_at,
            "created_at": shopping_list.created_at,
            "updated_at": shopping_list.updated_at,
            "sources": sources,
            "items": [_build_item_read(item) for item in sorted_items],
        }
    )


def _calculate_outdated_flag(db: Session, shopping_list: ShoppingList) -> bool:
    if shopping_list.source_type != "plan":
        return False
    if not shopping_list.sources:
        return False

    try:
        current_signature = _compute_plan_sources_signature(
            db,
            shopping_list.owner_user_id,
            [source.plan_id for source in shopping_list.sources],
        )
    except ShoppingPlanNotFoundError:
        return False

    return current_signature != (shopping_list.source_signature or "")


def _next_sort_order(db: Session, shopping_list_id: int) -> int:
    max_order = db.execute(
        select(func.max(ShoppingListItem.sort_order)).where(ShoppingListItem.shopping_list_id == shopping_list_id)
    ).scalar_one_or_none()
    if max_order is None:
        return 0
    return int(max_order) + 1


def _find_latest_shopping_list_for_plan(db: Session, user_id: int, plan_id: int) -> ShoppingList | None:
    return db.execute(
        select(ShoppingList)
        .join(ShoppingListSource, ShoppingListSource.shopping_list_id == ShoppingList.id)
        .where(
            ShoppingList.owner_user_id == user_id,
            ShoppingListSource.plan_id == plan_id,
        )
        .order_by(ShoppingList.created_at.desc(), ShoppingList.id.desc())
        .options(selectinload(ShoppingList.sources), selectinload(ShoppingList.items))
    ).scalars().first()


def create_shopping_list_from_plan(
    db: Session,
    user_id: int,
    payload: ShoppingListCreateFromPlanRequest,
) -> ShoppingListRead:
    plan = _get_plan_or_404(db, user_id, payload.plan_id, with_slots=True)

    grouped = _build_computed_food_totals(plan)
    source_signature = _compute_plan_sources_signature(db, user_id, [plan.id])

    shopping_list = ShoppingList(
        owner_user_id=user_id,
        title=payload.title or _build_plan_default_title(plan),
        status="active",
        source_type="plan",
        source_signature=source_signature,
        is_outdated=False,
    )
    db.add(shopping_list)
    db.flush()

    end_date = plan.start_date.fromordinal(plan.start_date.toordinal() + plan.days_count - 1)
    db.add(
        ShoppingListSource(
            shopping_list_id=shopping_list.id,
            plan_id=plan.id,
            date_from=plan.start_date,
            date_to=end_date,
        )
    )

    sorted_grouped = sorted(
        grouped.values(),
        key=lambda value: (str(value["name_snapshot"]).lower(), int(value["food_id"])),
    )

    for index, item in enumerate(sorted_grouped):
        planned_grams = _quantize_grams(item["planned_grams"])
        db.add(
            ShoppingListItem(
                shopping_list_id=shopping_list.id,
                food_id=item["food_id"],
                name_snapshot=item["name_snapshot"],
                category=item["category"],
                item_type="computed",
                planned_grams=planned_grams,
                adjusted_grams=None,
                unit="g",
                checked=False,
                excluded=False,
                sort_order=index,
            )
        )

    db.commit()
    return get_shopping_list(db, user_id, shopping_list.id)


def get_or_create_shopping_list_for_plan(
    db: Session,
    user_id: int,
    plan_id: int,
) -> ShoppingListRead:
    _get_plan_or_404(db, user_id, plan_id, with_slots=False)
    existing = _find_latest_shopping_list_for_plan(db, user_id, plan_id)
    if existing is not None:
        is_outdated = _calculate_outdated_flag(db, existing)
        return _build_shopping_list_read(existing, is_outdated=is_outdated)

    return create_shopping_list_from_plan(
        db,
        user_id,
        ShoppingListCreateFromPlanRequest(plan_id=plan_id),
    )


def get_shopping_list(
    db: Session,
    user_id: int,
    shopping_list_id: int,
) -> ShoppingListRead:
    shopping_list = _load_shopping_list_or_404(db, user_id, shopping_list_id, with_relations=True)
    is_outdated = _calculate_outdated_flag(db, shopping_list)
    return _build_shopping_list_read(shopping_list, is_outdated=is_outdated)


def delete_shopping_list(
    db: Session,
    user_id: int,
    shopping_list_id: int,
) -> None:
    shopping_list = _load_shopping_list_or_404(db, user_id, shopping_list_id, with_relations=True)
    db.delete(shopping_list)
    db.commit()


def delete_shopping_lists(
    db: Session,
    user_id: int,
    payload: ShoppingListBulkDeleteRequest,
) -> ShoppingListBulkDeleteResponse:
    unique_ids = sorted(set(payload.shopping_list_ids))
    lists = db.execute(
        select(ShoppingList)
        .where(
            ShoppingList.owner_user_id == user_id,
            ShoppingList.id.in_(unique_ids),
        )
        .options(selectinload(ShoppingList.sources), selectinload(ShoppingList.items))
    ).scalars().all()

    if len(lists) != len(unique_ids):
        raise ShoppingListNotFoundError("Shopping list not found")

    for shopping_list in lists:
        db.delete(shopping_list)

    db.commit()
    return ShoppingListBulkDeleteResponse(deleted_count=len(unique_ids))


def list_shopping_lists(
    db: Session,
    user_id: int,
) -> list[ShoppingListSummaryRead]:
    lists = db.execute(
        select(ShoppingList)
        .where(ShoppingList.owner_user_id == user_id)
        .order_by(ShoppingList.updated_at.desc(), ShoppingList.id.desc())
        .options(selectinload(ShoppingList.sources), selectinload(ShoppingList.items))
    ).scalars().all()

    payload: list[ShoppingListSummaryRead] = []
    for shopping_list in lists:
        source_plan_ids = sorted({source.plan_id for source in shopping_list.sources})
        is_outdated = _calculate_outdated_flag(db, shopping_list)
        payload.append(
            ShoppingListSummaryRead.model_validate(
                {
                    "id": shopping_list.id,
                    "owner_user_id": shopping_list.owner_user_id,
                    "title": shopping_list.title,
                    "status": shopping_list.status,
                    "source_type": shopping_list.source_type,
                    "source_signature": shopping_list.source_signature,
                    "is_outdated": is_outdated,
                    "generated_at": shopping_list.generated_at,
                    "created_at": shopping_list.created_at,
                    "updated_at": shopping_list.updated_at,
                    "source_plan_ids": source_plan_ids,
                    "items_total": len(shopping_list.items),
                }
            )
        )
    return payload


def update_shopping_list_item(
    db: Session,
    user_id: int,
    shopping_list_id: int,
    item_id: int,
    payload: ShoppingListItemUpdate,
) -> ShoppingListItemRead:
    _load_shopping_list_or_404(db, user_id, shopping_list_id, with_relations=False)
    item = db.execute(
        select(ShoppingListItem).where(
            ShoppingListItem.id == item_id,
            ShoppingListItem.shopping_list_id == shopping_list_id,
        )
    ).scalar_one_or_none()
    if item is None:
        raise ShoppingListItemNotFoundError("Shopping list item not found")

    update_data = payload.model_dump(exclude_unset=True)
    is_manual = item.item_type == "manual"

    if ("name_snapshot" in update_data or "unit" in update_data) and not is_manual:
        raise ShoppingItemUpdateForbiddenError("Only manual items can update name_snapshot or unit")

    if "checked" in update_data:
        item.checked = update_data["checked"]
    if "adjusted_grams" in update_data:
        item.adjusted_grams = update_data["adjusted_grams"]
    if "excluded" in update_data:
        item.excluded = update_data["excluded"]
    if "category" in update_data:
        item.category = update_data["category"]
    if "name_snapshot" in update_data:
        item.name_snapshot = update_data["name_snapshot"]
    if "unit" in update_data:
        item.unit = update_data["unit"]

    db.commit()
    db.refresh(item)
    return _build_item_read(item)


def add_manual_item(
    db: Session,
    user_id: int,
    shopping_list_id: int,
    payload: ShoppingManualItemCreate,
) -> ShoppingListItemRead:
    _load_shopping_list_or_404(db, user_id, shopping_list_id, with_relations=False)

    manual_item = ShoppingListItem(
        shopping_list_id=shopping_list_id,
        food_id=None,
        name_snapshot=payload.name,
        category=payload.category,
        item_type="manual",
        planned_grams=None,
        adjusted_grams=payload.adjusted_grams,
        unit=payload.unit,
        checked=False,
        excluded=False,
        sort_order=_next_sort_order(db, shopping_list_id),
    )
    db.add(manual_item)
    db.commit()
    db.refresh(manual_item)
    return _build_item_read(manual_item)


def merge_shopping_lists(
    db: Session,
    user_id: int,
    payload: ShoppingListMergeRequest,
) -> ShoppingListRead:
    source_lists = db.execute(
        select(ShoppingList)
        .where(
            ShoppingList.owner_user_id == user_id,
            ShoppingList.id.in_(payload.shopping_list_ids),
        )
        .options(selectinload(ShoppingList.sources), selectinload(ShoppingList.items).selectinload(ShoppingListItem.food))
    ).scalars().all()

    if len(source_lists) != len(payload.shopping_list_ids):
        raise ShoppingListNotFoundError("Shopping list not found")

    source_by_plan_id: dict[int, dict[str, object]] = {}
    for shopping_list in source_lists:
        for source in shopping_list.sources:
            existing = source_by_plan_id.get(source.plan_id)
            if existing is None:
                source_by_plan_id[source.plan_id] = {
                    "plan_id": source.plan_id,
                    "date_from": source.date_from,
                    "date_to": source.date_to,
                }
                continue
            if source.date_from is not None:
                existing_from = existing["date_from"]
                if existing_from is None or source.date_from < existing_from:
                    existing["date_from"] = source.date_from
            if source.date_to is not None:
                existing_to = existing["date_to"]
                if existing_to is None or source.date_to > existing_to:
                    existing["date_to"] = source.date_to

    plan_ids = sorted(source_by_plan_id)
    source_signature = _compute_plan_sources_signature(db, user_id, plan_ids)

    merged_list = ShoppingList(
        owner_user_id=user_id,
        title=payload.title or "Общий список покупок",
        status="active",
        source_type="plan",
        source_signature=source_signature,
        is_outdated=False,
    )
    db.add(merged_list)
    db.flush()

    for source_data in source_by_plan_id.values():
        db.add(
            ShoppingListSource(
                shopping_list_id=merged_list.id,
                plan_id=source_data["plan_id"],
                date_from=source_data["date_from"],
                date_to=source_data["date_to"],
            )
        )

    computed_by_food: dict[int, dict[str, object]] = {}
    manual_by_key: dict[tuple[str, str, str], dict[str, object]] = {}

    for shopping_list in source_lists:
        for item in shopping_list.items:
            if item.excluded or item.checked:
                continue

            quantity = item.adjusted_grams if item.adjusted_grams is not None else item.planned_grams
            if item.item_type == "computed" and item.food_id is not None:
                bucket = computed_by_food.get(item.food_id)
                if bucket is None:
                    food = item.food
                    bucket = {
                        "food_id": item.food_id,
                        "name_snapshot": food.name if food is not None else item.name_snapshot,
                        "category": food.category if food is not None else item.category,
                        "planned_grams": Decimal("0"),
                    }
                    computed_by_food[item.food_id] = bucket
                if quantity is not None:
                    bucket["planned_grams"] = bucket["planned_grams"] + quantity
                continue

            manual_key = (item.name_snapshot.strip().casefold(), item.unit.strip().casefold(), item.category)
            manual_bucket = manual_by_key.get(manual_key)
            if manual_bucket is None:
                manual_bucket = {
                    "name_snapshot": item.name_snapshot,
                    "category": item.category,
                    "unit": item.unit,
                    "adjusted_grams": None,
                }
                manual_by_key[manual_key] = manual_bucket

            if quantity is not None:
                current_quantity = manual_bucket["adjusted_grams"] or Decimal("0")
                manual_bucket["adjusted_grams"] = current_quantity + quantity

    sort_order = 0
    for item in sorted(computed_by_food.values(), key=lambda value: (str(value["name_snapshot"]).lower(), int(value["food_id"]))):
        if item["planned_grams"] <= 0:
            continue
        db.add(
            ShoppingListItem(
                shopping_list_id=merged_list.id,
                food_id=item["food_id"],
                name_snapshot=item["name_snapshot"],
                category=item["category"] or DEFAULT_FOOD_CATEGORY,
                item_type="computed",
                planned_grams=_quantize_grams(item["planned_grams"]),
                adjusted_grams=None,
                unit="g",
                checked=False,
                excluded=False,
                sort_order=sort_order,
            )
        )
        sort_order += 1

    for item in sorted(manual_by_key.values(), key=lambda value: (str(value["name_snapshot"]).lower(), str(value["unit"]).lower())):
        adjusted_grams = item["adjusted_grams"]
        db.add(
            ShoppingListItem(
                shopping_list_id=merged_list.id,
                food_id=None,
                name_snapshot=item["name_snapshot"],
                category=item["category"] or DEFAULT_FOOD_CATEGORY,
                item_type="manual",
                planned_grams=None,
                adjusted_grams=_quantize_grams(adjusted_grams) if adjusted_grams is not None else None,
                unit=item["unit"],
                checked=False,
                excluded=False,
                sort_order=sort_order,
            )
        )
        sort_order += 1

    db.commit()
    return get_shopping_list(db, user_id, merged_list.id)


def delete_shopping_list_item(
    db: Session,
    user_id: int,
    shopping_list_id: int,
    item_id: int,
) -> None:
    _load_shopping_list_or_404(db, user_id, shopping_list_id, with_relations=False)
    item = db.execute(
        select(ShoppingListItem).where(
            ShoppingListItem.id == item_id,
            ShoppingListItem.shopping_list_id == shopping_list_id,
        )
    ).scalar_one_or_none()
    if item is None:
        raise ShoppingListItemNotFoundError("Shopping list item not found")

    if item.item_type == "manual":
        db.delete(item)
    else:
        item.excluded = True

    db.commit()


def rebuild_shopping_list_from_sources(
    db: Session,
    user_id: int,
    shopping_list_id: int,
) -> ShoppingListRead:
    shopping_list = _load_shopping_list_or_404(db, user_id, shopping_list_id, with_relations=True)

    if shopping_list.source_type != "plan" or not shopping_list.sources:
        raise ShoppingListSourceNotSupportedError("Only shopping lists generated from a plan are supported")

    sorted_sources = sorted(shopping_list.sources, key=lambda source: source.id)
    source_plans = [_get_plan_or_404(db, user_id, source.plan_id, with_slots=True) for source in sorted_sources]

    grouped = _build_computed_food_totals_for_plans(source_plans)
    sorted_grouped = sorted(
        grouped.values(),
        key=lambda value: (str(value["name_snapshot"]).lower(), int(value["food_id"])),
    )

    existing_computed_by_food_id = {
        item.food_id: item
        for item in shopping_list.items
        if item.item_type == "computed" and item.food_id is not None
    }

    touched_food_ids: set[int] = set()
    for index, bucket in enumerate(sorted_grouped):
        food_id = int(bucket["food_id"])
        planned_grams = _quantize_grams(bucket["planned_grams"])

        existing = existing_computed_by_food_id.get(food_id)
        if existing is not None:
            existing.name_snapshot = bucket["name_snapshot"]
            existing.category = bucket["category"]
            existing.planned_grams = planned_grams
            existing.sort_order = index
            touched_food_ids.add(food_id)
            continue

        db.add(
            ShoppingListItem(
                shopping_list_id=shopping_list.id,
                food_id=food_id,
                name_snapshot=bucket["name_snapshot"],
                category=bucket["category"],
                item_type="computed",
                planned_grams=planned_grams,
                adjusted_grams=None,
                unit="g",
                checked=False,
                excluded=False,
                sort_order=index,
            )
        )
        touched_food_ids.add(food_id)

    for existing_food_id, existing in existing_computed_by_food_id.items():
        if existing_food_id not in touched_food_ids:
            db.delete(existing)

    source_signature = _compute_plan_sources_signature(db, user_id, [plan.id for plan in source_plans])
    shopping_list.source_signature = source_signature
    shopping_list.is_outdated = False
    shopping_list.generated_at = func.now()

    plan_by_id = {plan.id: plan for plan in source_plans}
    for source in sorted_sources:
        plan = plan_by_id[source.plan_id]
        end_date = plan.start_date.fromordinal(plan.start_date.toordinal() + plan.days_count - 1)
        source.date_from = plan.start_date
        source.date_to = end_date

    db.commit()
    return get_shopping_list(db, user_id, shopping_list.id)
