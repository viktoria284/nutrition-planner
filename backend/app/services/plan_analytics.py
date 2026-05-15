from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.schemas.plan import (
    NutrientAnalyticsRead,
    PlanAnalyticsResponse,
    PlanDayAnalyticsRead,
    PlanNutritionTargetRead,
    PlanPeriodAnalyticsRead,
)
from app.services.plans import PlanNotFoundError, build_plan_read, get_plan_for_user


class PlanAnalyticsTargetsMissingError(ValueError):
    pass


NUTRIENT_QUANT = Decimal("0.01")
PERCENT_QUANT = Decimal("0.1")


def _to_decimal(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _quantize_nutrient(value: Decimal) -> Decimal:
    return value.quantize(NUTRIENT_QUANT, rounding=ROUND_HALF_UP)


def _quantize_percent(value: Decimal) -> Decimal:
    return value.quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)


def _calculate_percent(total: Decimal, target: int | None) -> Decimal | None:
    if target is None or target <= 0:
        return None
    return _quantize_percent((total / Decimal(target)) * Decimal("100"))


def _resolve_status(*, nutrient: str, percent: Decimal | None, target: int | None) -> str:
    if target is None or target <= 0 or percent is None:
        return "no_target"

    if nutrient == "kcal":
        low, high = Decimal("90"), Decimal("110")
    elif nutrient == "fiber":
        low, high = Decimal("85"), Decimal("180")
    else:
        low, high = Decimal("85"), Decimal("115")

    if percent < low:
        return "low"
    if percent > high:
        return "high"
    return "ok"


def _outside_target_distance(*, nutrient: str, percent: Decimal | None, target: int | None) -> Decimal:
    if target is None or target <= 0 or percent is None:
        return Decimal("0")

    if nutrient == "kcal":
        low, high = Decimal("90"), Decimal("110")
    elif nutrient == "fiber":
        low, high = Decimal("85"), Decimal("180")
    else:
        low, high = Decimal("85"), Decimal("115")

    if percent < low:
        return low - percent
    if percent > high:
        return percent - high
    return Decimal("0")


def _score_from_percents(*, kcal: Decimal | None, protein: Decimal | None, fat: Decimal | None, carbs: Decimal | None, fiber: Decimal | None, target_fiber: int | None) -> int:
    penalty = Decimal("0")

    components = [
        ("kcal", kcal, 30, Decimal("40"), 1),
        ("protein", protein, 24, Decimal("45"), 1),
        ("fat", fat, 18, Decimal("45"), 1),
        ("carbs", carbs, 18, Decimal("45"), 1),
    ]
    if target_fiber is not None and target_fiber > 0:
        components.append(("fiber", fiber, 10, Decimal("120"), target_fiber))

    for nutrient, percent, weight, divisor, target in components:
        outside = _outside_target_distance(nutrient=nutrient, percent=percent, target=target)
        if outside <= 0:
            continue
        ratio = min(Decimal("1"), outside / divisor)
        penalty += Decimal(weight) * ratio

    raw_score = Decimal("100") - penalty
    if raw_score < 0:
        raw_score = Decimal("0")
    if raw_score > 100:
        raw_score = Decimal("100")
    return int(raw_score.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _status_phrase(nutrient_label: str, status: str) -> str:
    if status == "ok":
        return f"{nutrient_label} близко к цели."
    if status == "low":
        return f"{nutrient_label} в среднем ниже цели."
    if status == "high":
        return f"{nutrient_label} в среднем выше цели."
    return f"Для {nutrient_label.lower()} цель не задана."


def _build_recommendations(*, days: list[PlanDayAnalyticsRead], period: PlanPeriodAnalyticsRead, targets: PlanNutritionTargetRead) -> list[str]:
    recommendations: list[str] = []

    if period.overall_score >= 85:
        recommendations.append("План выглядит сбалансированным по основным показателям.")
    elif period.overall_score >= 70:
        recommendations.append("План в целом близок к целям, но по отдельным дням есть отклонения.")
    else:
        recommendations.append("План можно точечно скорректировать, чтобы приблизить средние к целям.")

    kcal_status = _resolve_status(nutrient="kcal", percent=period.kcal_percent, target=targets.kcal)
    if kcal_status == "low":
        recommendations.append("Средняя калорийность ниже цели — можно увеличить порции или добавить перекус.")
    elif kcal_status == "high":
        recommendations.append("Средняя калорийность выше цели — можно немного уменьшить порции в отдельных днях.")
    else:
        recommendations.append("Средняя калорийность близка к цели.")

    day_kcal_with_percent = [
        (
            day.date.isoformat(),
            day.kcal.percent,
            _outside_target_distance(nutrient="kcal", percent=day.kcal.percent, target=targets.kcal),
        )
        for day in days
        if day.kcal.percent is not None
    ]
    if day_kcal_with_percent:
        day_iso, day_percent, day_distance = max(day_kcal_with_percent, key=lambda item: item[2])
        if day_distance >= Decimal("8") and day_percent is not None:
            direction = "ниже" if day_percent < Decimal("100") else "выше"
            recommendations.append(f"Самое заметное отклонение по калориям — {day_iso}: {day_percent}% от цели ({direction} цели).")

    macro_items: list[tuple[str, Decimal | None, int | None]] = [
        ("Белок", period.protein_percent, targets.protein),
        ("Жиры", period.fat_percent, targets.fat),
        ("Углеводы", period.carbs_percent, targets.carbs),
    ]
    macro_candidates = [
        (
            label,
            _outside_target_distance(nutrient=label.lower(), percent=percent, target=target),
            _resolve_status(nutrient=label.lower(), percent=percent, target=target),
        )
        for label, percent, target in macro_items
        if target is not None and target > 0 and percent is not None
    ]
    if macro_candidates:
        label, _distance, status = max(macro_candidates, key=lambda item: item[1])
        if status == "ok":
            recommendations.append("Белки, жиры и углеводы в среднем близки к целям.")
        elif status == "low":
            if label == "Белок":
                recommendations.append("Белок ниже цели — можно чаще выбирать блюда с птицей, рыбой, яйцами, творогом или бобовыми.")
            elif label == "Жиры":
                recommendations.append("Жиры ниже цели — можно добавить немного орехов, масла или более сытный гарнир.")
            else:
                recommendations.append("Углеводы ниже цели — можно добавить крупу, цельнозерновой хлеб или фрукт.")
        else:
            if label == "Белок":
                recommendations.append("Белок выше цели в отдельных днях — можно немного уменьшить порции белковых блюд.")
            elif label == "Жиры":
                recommendations.append("Жиры выше цели — можно уменьшить масло, сыр или жирные ингредиенты в отдельных слотах.")
            else:
                recommendations.append("Углеводы выше цели в отдельных днях — можно сократить порцию гарнира или сладких перекусов.")

    if targets.fiber is not None and targets.fiber > 0:
        fiber_status = _resolve_status(nutrient="fiber", percent=period.fiber_percent, target=targets.fiber)
        if fiber_status == "ok":
            recommendations.append("Клетчатка в среднем близка к ориентиру.")
        elif fiber_status == "low":
            recommendations.append("Клетчатка ниже ориентира — можно добавить овощи, фрукты или бобовые.")
        else:
            recommendations.append("Клетчатка выше ориентира из-за блюд с овощами, бобовыми и крупами.")

    unique_recommendations: list[str] = []
    for item in recommendations:
        if item in unique_recommendations:
            continue
        unique_recommendations.append(item)

    if len(unique_recommendations) < 3:
        unique_recommendations.append("План можно скорректировать заменой отдельных ингредиентов.")

    return unique_recommendations[:5]


def get_plan_analytics_for_user(db: Session, *, user_id: int, plan_id: int) -> PlanAnalyticsResponse:
    plan = get_plan_for_user(db, user_id, plan_id)
    plan_read = build_plan_read(plan)

    targets = PlanNutritionTargetRead(
        kcal=plan_read.target_kcal,
        protein=plan_read.target_protein,
        fat=plan_read.target_fat,
        carbs=plan_read.target_carbs,
        fiber=plan_read.target_fiber,
    )

    if all(value is None or value <= 0 for value in [targets.kcal, targets.protein, targets.fat, targets.carbs, targets.fiber]):
        raise PlanAnalyticsTargetsMissingError("Для оценки плана нужны цели профиля.")

    days_count = len(plan_read.days)
    total_kcal = sum((_to_decimal(day.totals.kcal) for day in plan_read.days), Decimal("0"))
    total_protein = sum((_to_decimal(day.totals.protein) for day in plan_read.days), Decimal("0"))
    total_fat = sum((_to_decimal(day.totals.fat) for day in plan_read.days), Decimal("0"))
    total_carbs = sum((_to_decimal(day.totals.carbs) for day in plan_read.days), Decimal("0"))
    total_fiber = sum((_to_decimal(day.totals.fiber) for day in plan_read.days), Decimal("0"))

    denominator = Decimal(days_count) if days_count > 0 else Decimal("1")
    average_kcal = _quantize_nutrient(total_kcal / denominator)
    average_protein = _quantize_nutrient(total_protein / denominator)
    average_fat = _quantize_nutrient(total_fat / denominator)
    average_carbs = _quantize_nutrient(total_carbs / denominator)
    average_fiber = _quantize_nutrient(total_fiber / denominator)

    kcal_percent = _calculate_percent(average_kcal, targets.kcal)
    protein_percent = _calculate_percent(average_protein, targets.protein)
    fat_percent = _calculate_percent(average_fat, targets.fat)
    carbs_percent = _calculate_percent(average_carbs, targets.carbs)
    fiber_percent = _calculate_percent(average_fiber, targets.fiber)

    period_summary = PlanPeriodAnalyticsRead(
        days_count=days_count,
        average_kcal=average_kcal,
        average_protein=average_protein,
        average_fat=average_fat,
        average_carbs=average_carbs,
        average_fiber=average_fiber,
        kcal_percent=kcal_percent,
        protein_percent=protein_percent,
        fat_percent=fat_percent,
        carbs_percent=carbs_percent,
        fiber_percent=fiber_percent,
        overall_score=_score_from_percents(
            kcal=kcal_percent,
            protein=protein_percent,
            fat=fat_percent,
            carbs=carbs_percent,
            fiber=fiber_percent,
            target_fiber=targets.fiber,
        ),
    )

    day_analytics: list[PlanDayAnalyticsRead] = []
    for day in plan_read.days:
        day_kcal_total = _to_decimal(day.totals.kcal)
        day_protein_total = _to_decimal(day.totals.protein)
        day_fat_total = _to_decimal(day.totals.fat)
        day_carbs_total = _to_decimal(day.totals.carbs)
        day_fiber_total = _to_decimal(day.totals.fiber)

        day_kcal_percent = _calculate_percent(day_kcal_total, targets.kcal)
        day_protein_percent = _calculate_percent(day_protein_total, targets.protein)
        day_fat_percent = _calculate_percent(day_fat_total, targets.fat)
        day_carbs_percent = _calculate_percent(day_carbs_total, targets.carbs)
        day_fiber_percent = _calculate_percent(day_fiber_total, targets.fiber)

        day_analytics.append(
            PlanDayAnalyticsRead(
                date=day.date,
                kcal=NutrientAnalyticsRead(
                    total=_quantize_nutrient(day_kcal_total),
                    percent=day_kcal_percent,
                    status=_resolve_status(nutrient="kcal", percent=day_kcal_percent, target=targets.kcal),
                ),
                protein=NutrientAnalyticsRead(
                    total=_quantize_nutrient(day_protein_total),
                    percent=day_protein_percent,
                    status=_resolve_status(nutrient="protein", percent=day_protein_percent, target=targets.protein),
                ),
                fat=NutrientAnalyticsRead(
                    total=_quantize_nutrient(day_fat_total),
                    percent=day_fat_percent,
                    status=_resolve_status(nutrient="fat", percent=day_fat_percent, target=targets.fat),
                ),
                carbs=NutrientAnalyticsRead(
                    total=_quantize_nutrient(day_carbs_total),
                    percent=day_carbs_percent,
                    status=_resolve_status(nutrient="carbs", percent=day_carbs_percent, target=targets.carbs),
                ),
                fiber=NutrientAnalyticsRead(
                    total=_quantize_nutrient(day_fiber_total),
                    percent=day_fiber_percent,
                    status=_resolve_status(nutrient="fiber", percent=day_fiber_percent, target=targets.fiber),
                ),
                day_score=_score_from_percents(
                    kcal=day_kcal_percent,
                    protein=day_protein_percent,
                    fat=day_fat_percent,
                    carbs=day_carbs_percent,
                    fiber=day_fiber_percent,
                    target_fiber=targets.fiber,
                ),
            )
        )

    recommendations = _build_recommendations(days=day_analytics, period=period_summary, targets=targets)

    return PlanAnalyticsResponse(
        targets=targets,
        period_summary=period_summary,
        day_analytics=day_analytics,
        recommendations=recommendations,
    )
