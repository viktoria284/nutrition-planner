from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.plan import Plan
from app.models.plan_slot import PlanSlot
from app.schemas.plan import PlanCreate, PlanListItem, PlanRead, PlanSlotRead, PlanSlotUpdate
from app.services.recipes import get_accessible_recipe_by_id


class PlanNotFoundError(ValueError):
    pass


class PlanSlotNotFoundError(ValueError):
    pass


class PlanSlotRecipeNotFoundError(ValueError):
    pass


def _sort_slots(slots: list[PlanSlot]) -> list[PlanSlot]:
    return sorted(
        slots,
        key=lambda slot: (slot.day_date, slot.slot_index, slot.id),
    )


def _get_plan_or_404(db: Session, user_id: int, plan_id: int, *, with_slots: bool = False) -> Plan:
    stmt = select(Plan).where(
        Plan.id == plan_id,
        Plan.owner_user_id == user_id,
    )
    if with_slots:
        stmt = stmt.options(selectinload(Plan.slots))

    plan = db.execute(stmt).scalar_one_or_none()
    if not plan:
        raise PlanNotFoundError("Plan not found")
    return plan


def build_plan_read(plan: Plan) -> PlanRead:
    sorted_slots = _sort_slots(list(plan.slots))
    return PlanRead.model_validate(
        {
            "id": plan.id,
            "owner_user_id": plan.owner_user_id,
            "start_date": plan.start_date,
            "days_count": plan.days_count,
            "meals_per_day": plan.meals_per_day,
            "title": plan.title,
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
            "slots": [PlanSlotRead.model_validate(slot) for slot in sorted_slots],
        }
    )


def list_plans_for_user(db: Session, user_id: int) -> list[Plan]:
    return db.execute(
        select(Plan)
        .where(Plan.owner_user_id == user_id)
        .order_by(Plan.updated_at.desc(), Plan.id.desc())
    ).scalars().all()


def build_plan_list_item(plan: Plan) -> PlanListItem:
    return PlanListItem.model_validate(plan)


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
    db.refresh(slot)
    return slot
