from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.plan import Plan
from app.models.plan_slot import PlanSlot
from app.models.user import User


def _create_user(db_session: Session, *, suffix: str) -> User:
    user = User(
        email=f"plan-user-{suffix}@example.com",
        username=f"plan_user_{suffix}",
        hashed_password="hashed",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_plan(
    db_session: Session,
    *,
    owner_user_id: int,
    start_date_value: date = date(2026, 3, 24),
    days_count: int = 7,
    meals_per_day: int = 3,
) -> Plan:
    plan = Plan(
        owner_user_id=owner_user_id,
        start_date=start_date_value,
        days_count=days_count,
        meals_per_day=meals_per_day,
        title="Test Plan",
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


def test_plan_tables_are_registered_in_metadata() -> None:
    assert "plans" in Base.metadata.tables
    assert "plan_slots" in Base.metadata.tables


@pytest.mark.parametrize("invalid_days_count", [0, 8])
def test_plan_days_count_constraint(invalid_days_count: int, db_session_factory: sessionmaker[Session]) -> None:
    db_session = db_session_factory()
    try:
        user = _create_user(db_session, suffix=f"days_{invalid_days_count}")
        db_session.add(
            Plan(
                owner_user_id=user.id,
                start_date=date(2026, 3, 24),
                days_count=invalid_days_count,
                meals_per_day=3,
            )
        )
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
    finally:
        db_session.close()


@pytest.mark.parametrize("invalid_meals_per_day", [1, 7])
def test_plan_meals_per_day_constraint(invalid_meals_per_day: int, db_session_factory: sessionmaker[Session]) -> None:
    db_session = db_session_factory()
    try:
        user = _create_user(db_session, suffix=f"meals_{invalid_meals_per_day}")
        db_session.add(
            Plan(
                owner_user_id=user.id,
                start_date=date(2026, 3, 24),
                days_count=7,
                meals_per_day=invalid_meals_per_day,
            )
        )
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
    finally:
        db_session.close()


@pytest.mark.parametrize("invalid_multiplier", [Decimal("0"), Decimal("-0.5")])
def test_plan_slot_servings_multiplier_constraint(
    invalid_multiplier: Decimal,
    db_session_factory: sessionmaker[Session],
) -> None:
    db_session = db_session_factory()
    try:
        user = _create_user(db_session, suffix="multiplier")
        plan = _create_plan(db_session, owner_user_id=user.id)

        db_session.add(
            PlanSlot(
                plan_id=plan.id,
                day_date=plan.start_date,
                slot_index=0,
                servings_multiplier=invalid_multiplier,
            )
        )

        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
    finally:
        db_session.close()


def test_plan_slot_unique_constraint(db_session_factory: sessionmaker[Session]) -> None:
    db_session = db_session_factory()
    try:
        user = _create_user(db_session, suffix="unique")
        plan = _create_plan(db_session, owner_user_id=user.id)

        first_slot = PlanSlot(
            plan_id=plan.id,
            day_date=plan.start_date,
            slot_index=1,
        )
        db_session.add(first_slot)
        db_session.commit()

        db_session.add(
            PlanSlot(
                plan_id=plan.id,
                day_date=plan.start_date,
                slot_index=1,
            )
        )
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
    finally:
        db_session.close()


def test_plan_slot_orm_defaults_applied(db_session_factory: sessionmaker[Session]) -> None:
    db_session = db_session_factory()
    try:
        user = _create_user(db_session, suffix="defaults")
        plan = _create_plan(db_session, owner_user_id=user.id)

        slot = PlanSlot(
            plan_id=plan.id,
            day_date=plan.start_date,
            slot_index=0,
        )
        db_session.add(slot)
        db_session.commit()
        db_session.refresh(slot)

        assert slot.pinned is False
        assert slot.servings_multiplier == Decimal("1")
    finally:
        db_session.close()
