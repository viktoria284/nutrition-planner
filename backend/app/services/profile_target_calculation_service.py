from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.profile import Profile
from app.models.profile_target_calculation import ProfileTargetCalculation
from app.schemas.profile_target_calculation import ProfileTargetCalculationCreate

ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

GOAL_FACTORS = {
    "maintain": 1.0,
    "lose": 0.85,
    "gain": 1.10,
}

MACRO_RATIOS = {
    "balanced": (0.20, 0.30, 0.50),
    "higher_protein": (0.25, 0.30, 0.45),
    "higher_carb": (0.20, 0.25, 0.55),
}

LOW_KCAL_WARNING_MESSAGE = (
    "Полученная калорийность выглядит низкой, поэтому перед использованием цели рекомендуется "
    "проверить её вручную."
)
BREASTFEEDING_WARNING_MESSAGE = (
    "При грудном вскармливании потребность в энергии может быть выше. "
    "В калькуляторе добавлена ориентировочная прибавка к калорийности, но расчёт не является медицинской "
    "рекомендацией и не заменяет консультацию специалиста."
)
PREGNANCY_WARNING_MESSAGE = (
    "Во время беременности потребность в энергии и нутриентах зависит от срока, состояния здоровья и "
    "рекомендаций врача. Система не рассчитывает питание для беременности автоматически и не заменяет "
    "консультацию специалиста."
)
MEDICAL_SPECIAL_DIET_WARNING_MESSAGE = (
    "При состояниях, требующих лечебного питания, расчёт является только ориентировочным. "
    "Система не назначает лечебные диеты. Необходимо проконсультироваться со специалистом."
)
BREASTFEEDING_KCAL_BONUS = {
    "first_6_months": 330,
    "after_6_months": 400,
    "unknown": 330,
}


class ProfileTargetCalculationNotFoundError(ValueError):
    pass


class ProfileNotFoundError(ValueError):
    pass


def _round_int(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _round_tenth(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _calculate_bmr(payload: ProfileTargetCalculationCreate) -> float:
    if payload.formula == "mifflin_st_jeor":
        if payload.sex == "male":
            return (10 * payload.weight_kg) + (6.25 * payload.height_cm) - (5 * payload.age) + 5
        return (10 * payload.weight_kg) + (6.25 * payload.height_cm) - (5 * payload.age) - 161

    if payload.formula == "revised_harris_benedict":
        if payload.sex == "male":
            return 88.362 + (13.397 * payload.weight_kg) + (4.799 * payload.height_cm) - (5.677 * payload.age)
        return 447.593 + (9.247 * payload.weight_kg) + (3.098 * payload.height_cm) - (4.330 * payload.age)

    # WHO / FAO / UNU
    if payload.age < 30:
        return (15.3 * payload.weight_kg) + 679 if payload.sex == "male" else (14.7 * payload.weight_kg) + 496
    if payload.age < 60:
        return (11.6 * payload.weight_kg) + 879 if payload.sex == "male" else (8.7 * payload.weight_kg) + 829
    return (13.5 * payload.weight_kg) + 487 if payload.sex == "male" else (10.5 * payload.weight_kg) + 596


def _build_warning_message(
    *,
    payload: ProfileTargetCalculationCreate,
    target_kcal: int,
) -> str | None:
    is_low_kcal = (
        payload.sex == "female" and target_kcal < 1200
    ) or (
        payload.sex == "male" and target_kcal < 1500
    )

    messages: list[str] = []
    if payload.special_condition == "breastfeeding":
        messages.append(BREASTFEEDING_WARNING_MESSAGE)
    elif payload.special_condition == "pregnant":
        messages.append(PREGNANCY_WARNING_MESSAGE)
    elif payload.special_condition == "medical_special_diet":
        messages.append(MEDICAL_SPECIAL_DIET_WARNING_MESSAGE)
    if is_low_kcal:
        messages.append(LOW_KCAL_WARNING_MESSAGE)

    if not messages:
        return None
    return " ".join(messages)


def _get_profile_for_user(db: Session, *, user_id: int, profile_id: int) -> Profile | None:
    return db.execute(
        select(Profile).where(Profile.id == profile_id, Profile.user_id == user_id)
    ).scalar_one_or_none()


def get_latest_calculation_for_user(db: Session, *, user_id: int) -> ProfileTargetCalculation | None:
    return db.execute(
        select(ProfileTargetCalculation).where(ProfileTargetCalculation.user_id == user_id)
    ).scalar_one_or_none()


def calculate_and_save_for_user(
    db: Session,
    *,
    user_id: int,
    payload: ProfileTargetCalculationCreate,
) -> ProfileTargetCalculation:
    activity_factor = ACTIVITY_FACTORS[payload.activity_level]
    goal_factor = GOAL_FACTORS[payload.goal]
    protein_ratio, fat_ratio, carbs_ratio = MACRO_RATIOS[payload.macro_preset]

    bmr_raw = _calculate_bmr(payload)
    tdee_raw = bmr_raw * activity_factor
    target_kcal_raw = tdee_raw * goal_factor
    if payload.special_condition == "breastfeeding":
        lactation_period = payload.lactation_period or "unknown"
        target_kcal_raw += BREASTFEEDING_KCAL_BONUS[lactation_period]

    bmr = _round_int(bmr_raw)
    tdee = _round_int(tdee_raw)
    target_kcal = _round_int(target_kcal_raw)

    target_protein = _round_tenth((target_kcal * protein_ratio) / 4)
    target_fat = _round_tenth((target_kcal * fat_ratio) / 9)
    target_carbs = _round_tenth((target_kcal * carbs_ratio) / 4)
    target_fiber = _round_tenth(25)

    warning_message = _build_warning_message(payload=payload, target_kcal=target_kcal)

    existing = get_latest_calculation_for_user(db, user_id=user_id)
    if existing is None:
        calculation = ProfileTargetCalculation(
            user_id=user_id,
            sex=payload.sex,
            age=payload.age,
            height_cm=payload.height_cm,
            weight_kg=payload.weight_kg,
            activity_level=payload.activity_level,
            goal=payload.goal,
            formula=payload.formula,
            macro_preset=payload.macro_preset,
            special_condition=payload.special_condition,
            lactation_period=payload.lactation_period,
            bmr=bmr,
            tdee=tdee,
            target_kcal=target_kcal,
            target_protein=target_protein,
            target_fat=target_fat,
            target_carbs=target_carbs,
            target_fiber=target_fiber,
            warning_message=warning_message,
        )
        db.add(calculation)
    else:
        calculation = existing
        calculation.sex = payload.sex
        calculation.age = payload.age
        calculation.height_cm = payload.height_cm
        calculation.weight_kg = payload.weight_kg
        calculation.activity_level = payload.activity_level
        calculation.goal = payload.goal
        calculation.formula = payload.formula
        calculation.macro_preset = payload.macro_preset
        calculation.special_condition = payload.special_condition
        calculation.lactation_period = payload.lactation_period
        calculation.bmr = bmr
        calculation.tdee = tdee
        calculation.target_kcal = target_kcal
        calculation.target_protein = target_protein
        calculation.target_fat = target_fat
        calculation.target_carbs = target_carbs
        calculation.target_fiber = target_fiber
        calculation.warning_message = warning_message

    db.commit()
    db.refresh(calculation)
    return calculation


def apply_latest_calculation_to_profile(
    db: Session,
    *,
    user_id: int,
    profile_id: int,
) -> Profile:
    latest = get_latest_calculation_for_user(db, user_id=user_id)
    if latest is None:
        raise ProfileTargetCalculationNotFoundError("Сначала выполните расчёт в калькуляторе КБЖУ.")

    profile = _get_profile_for_user(db, user_id=user_id, profile_id=profile_id)
    if profile is None:
        raise ProfileNotFoundError("Profile not found")

    profile.target_kcal = latest.target_kcal
    profile.target_protein = _round_int(float(latest.target_protein))
    profile.target_fat = _round_int(float(latest.target_fat))
    profile.target_carbs = _round_int(float(latest.target_carbs))
    profile.target_fiber = _round_int(float(latest.target_fiber))

    db.commit()
    db.refresh(profile)
    return profile
