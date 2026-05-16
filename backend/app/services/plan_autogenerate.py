from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
import re

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.plan import Plan
from app.models.plan_slot import PlanSlot, PlanSlotIngredientOverride
from app.models.profile import Profile
from app.models.recipe import Recipe, RecipeIngredient
from app.schemas.plan import (
    PlanAutogenerateRequest,
    RegeneratePlanDayRequest,
    ReplacePlanSlotRequest,
)
from app.services.plan_slot_ingredients import clear_slot_ingredient_overrides
from app.services.recipes import (
    build_accessible_recipes_condition,
    calculate_recipe_nutrients,
    list_favorite_recipe_ids,
)


@dataclass(frozen=True)
class SlotTemplate:
    meal_type: str
    weight: Decimal


@dataclass(frozen=True)
class PlanTargets:
    kcal: Decimal | None
    protein: Decimal | None
    fat: Decimal | None
    carbs: Decimal | None
    fiber: Decimal | None


@dataclass(frozen=True)
class RecipeScore:
    total_score: Decimal
    repeat_penalty: Decimal
    calorie_penalty: Decimal
    macro_penalty: Decimal
    slot_penalty: Decimal


@dataclass(frozen=True)
class CandidateOption:
    recipe: Recipe
    servings_multiplier: Decimal
    nutrients: dict[str, Decimal]


@dataclass(frozen=True)
class FeasibilityEstimate:
    max_daily_kcal: Decimal
    max_daily_protein: Decimal
    max_daily_fat: Decimal
    max_daily_carbs: Decimal
    max_daily_fiber: Decimal


@dataclass(frozen=True)
class AutoplanPreferences:
    excluded_food_ids: set[int]
    excluded_categories: set[str]
    excluded_terms: set[str]
    preferred_food_ids: set[int]
    preferred_categories: set[str]
    favorite_recipe_ids: set[int]
    favorite_recipes_mode: str
    max_cook_time_minutes: int | None
    batch_cooking: dict[str, int]


SLOT_TEMPLATES_BY_MEALS_PER_DAY: dict[int, tuple[SlotTemplate, ...]] = {
    2: (
        SlotTemplate(meal_type="lunch", weight=Decimal("0.45")),
        SlotTemplate(meal_type="dinner", weight=Decimal("0.55")),
    ),
    3: (
        SlotTemplate(meal_type="breakfast", weight=Decimal("0.25")),
        SlotTemplate(meal_type="lunch", weight=Decimal("0.40")),
        SlotTemplate(meal_type="dinner", weight=Decimal("0.35")),
    ),
    4: (
        SlotTemplate(meal_type="breakfast", weight=Decimal("0.25")),
        SlotTemplate(meal_type="lunch", weight=Decimal("0.35")),
        SlotTemplate(meal_type="dinner", weight=Decimal("0.30")),
        SlotTemplate(meal_type="snack", weight=Decimal("0.10")),
    ),
    5: (
        SlotTemplate(meal_type="breakfast", weight=Decimal("0.20")),
        SlotTemplate(meal_type="snack", weight=Decimal("0.10")),
        SlotTemplate(meal_type="lunch", weight=Decimal("0.30")),
        SlotTemplate(meal_type="dinner", weight=Decimal("0.25")),
        SlotTemplate(meal_type="snack", weight=Decimal("0.15")),
    ),
    6: (
        SlotTemplate(meal_type="breakfast", weight=Decimal("0.20")),
        SlotTemplate(meal_type="snack", weight=Decimal("0.10")),
        SlotTemplate(meal_type="lunch", weight=Decimal("0.25")),
        SlotTemplate(meal_type="snack", weight=Decimal("0.10")),
        SlotTemplate(meal_type="dinner", weight=Decimal("0.25")),
        SlotTemplate(meal_type="snack", weight=Decimal("0.10")),
    ),
}

SERVINGS_MULTIPLIER_CANDIDATES: tuple[Decimal, ...] = (
    Decimal("0.75"),
    Decimal("1.00"),
    Decimal("1.25"),
    Decimal("1.50"),
    Decimal("1.75"),
    Decimal("2.00"),
)

CALORIE_PENALTY_WEIGHT = Decimal("120")
MACRO_PENALTY_WEIGHT = Decimal("28")
PROTEIN_OVERSHOOT_WEIGHT = Decimal("220")
FAT_OVERSHOOT_WEIGHT = Decimal("90")
FAT_UNDERSHOOT_WEIGHT = Decimal("145")
CARBS_UNDERSHOOT_WEIGHT = Decimal("180")
FIBER_UNDERSHOOT_WEIGHT = Decimal("55")
FIBER_OVERSHOOT_WEIGHT = Decimal("22")
FIBER_OVERSHOOT_MARGIN_GRAMS = Decimal("20")
REMAINING_BALANCE_WEIGHT = Decimal("130")
MACRO_PROFILE_PENALTY_WEIGHT = Decimal("140")
FAT_PROFILE_PENALTY_WEIGHT = Decimal("120")
REPEAT_USAGE_PENALTY = Decimal("18")
REPEAT_SAME_SLOT_BY_DISTANCE: dict[int, Decimal] = {
    1: Decimal("120"),
    2: Decimal("70"),
    3: Decimal("30"),
    4: Decimal("12"),
}
FAR_REPEAT_SAME_SLOT_PENALTY = Decimal("4")
SLOT_MISMATCH_PENALTY = Decimal("10000")
HUGE_GUARDRAIL_PENALTY = Decimal("2500")
LARGE_SLOT_WEIGHT_THRESHOLD = Decimal("0.25")
PROTEIN_OVERSHOOT_HARD_LIMIT = Decimal("1.35")
CARBS_SO_FAR_GUARDRAIL_RATIO = Decimal("0.65")
PROTEIN_DENSE_MULTIPLIER_THRESHOLD = Decimal("1.50")
PROTEIN_DENSE_PER_SERVING_THRESHOLD = Decimal("35")
LOW_CARB_PER_SERVING_THRESHOLD = Decimal("22")
PROTEIN_DENSE_MULTIPLIER_CAP = Decimal("1.50")
DRY_LOW_FAT_SHARE_THRESHOLD = Decimal("0.16")
FAT_FRIENDLY_SHARE_THRESHOLD = Decimal("0.28")
FAT_FRIENDLY_FAT_GRAMS_THRESHOLD = Decimal("12")
REPEAT_PENALTY_CAP_FLOOR = Decimal("85")
REPEAT_PENALTY_CAP_BY_MACRO_FIT_FACTOR = Decimal("0.45")
LOW_FEASIBILITY_KCAL_GAP_RATIO = Decimal("0.18")
LOW_FEASIBILITY_CARBS_GAP_RATIO = Decimal("0.20")
LOW_FEASIBILITY_FAT_GAP_RATIO = Decimal("0.20")
HIGH_TARGET_KCAL_RISK_THRESHOLD = Decimal("3200")
HIGH_FAT_OVERSHOOT_RATIO = Decimal("0.18")
HIGH_FAT_OVERSHOOT_EXTRA_WEIGHT = Decimal("170")
KCAL_CLOSE_TO_EXPECTED_RATIO = Decimal("0.12")
CARBS_NEAR_TARGET_UNDERSHOOT_RATIO = Decimal("0.12")
CARBS_NEAR_TARGET_EXTRA_WEIGHT = Decimal("140")
SNACK_SLOT_TARGET_CAP_RATIO_5_PLUS = Decimal("1.22")
SNACK_SLOT_TARGET_CAP_RATIO_DEFAULT = Decimal("1.30")
BREAKFAST_SLOT_TARGET_CAP_RATIO_5_PLUS = Decimal("1.32")
BREAKFAST_SLOT_TARGET_CAP_RATIO_DEFAULT = Decimal("1.40")
MAIN_SLOT_TARGET_CAP_RATIO = Decimal("1.55")
SLOT_GUARDRAIL_PENALTY_WEIGHT = Decimal("420")
DAY_VARIATION_WORSENING_FACTOR = Decimal("1.12")
DAY_VARIATION_WORSENING_MARGIN = Decimal("14")
DAY_VARIATION_SCORE_WEIGHT = Decimal("130")
DAY_KCAL_OVERSHOOT_GUARDRAIL_WEIGHT = Decimal("180")
DAY_VARIATION_KCAL_WORSENING_RATIO = Decimal("0.08")
MEDIUM_PROFILE_KCAL_THRESHOLD = Decimal("2800")
MEDIUM_PROFILE_OVER_KCAL_TRIGGER = Decimal("0.05")
MEDIUM_PROFILE_PROTEIN_FAT_EXTRA_WEIGHT = Decimal("210")
DAY_EXTREME_KCAL_RATIO = Decimal("1.12")
DAY_EXTREME_PROTEIN_RATIO = Decimal("1.25")
DAY_EXTREME_FAT_RATIO = Decimal("1.25")
HIGH_CARB_TARGET_THRESHOLD = Decimal("450")
HIGH_CARB_PROFILE_CARBS_EXTRA_WEIGHT = Decimal("180")
HIGH_CARB_PROFILE_PROTEIN_HEAVY_WEIGHT = Decimal("190")
HIGH_CARB_PROFILE_LOW_CARB_GUARDRAIL_RATIO = Decimal("0.82")
HIGH_CARB_PROFILE_PROTEIN_OVERSHOOT_RATIO = Decimal("1.15")
DAY_PATTERN_PREFIX_PENALTY = Decimal("10")
DAY_PATTERN_EXACT_REPEAT_PENALTY = Decimal("260")
RECIPE_NAME_SIMILARITY_THRESHOLD = Decimal("0.65")
RECIPE_NAME_SIMILARITY_PENALTY = Decimal("800")
PREFERRED_FOOD_BONUS = Decimal("38")
PREFERRED_CATEGORY_BONUS = Decimal("16")
PREFERRED_BONUS_CAP = Decimal("140")
FAVORITE_RECIPE_BONUS = Decimal("42")
UNKNOWN_COOK_TIME_PENALTY_WHEN_LIMITED = Decimal("12")
BATCH_ONE_RECENT_REPEAT_PENALTY_BY_DISTANCE: dict[int, Decimal] = {
    1: Decimal("320"),
    2: Decimal("220"),
    3: Decimal("140"),
}
BATCH_ONE_SAME_DAY_CROSS_SLOT_REPEAT_PENALTY = Decimal("240")
BATCH_ONE_MAX_REPEAT_PER_SLOT_IN_7_DAYS = 2
BATCH_ONE_REPEAT_OVERUSE_PENALTY = Decimal("560")
MAIN_INGREDIENT_GROUP_PENALTY_BY_GROUP: dict[str, Decimal] = {
    "fish": Decimal("85"),
    "tofu": Decimal("105"),
    "legume": Decimal("70"),
}
DIVERSITY_PRECHECK_FRIENDLY_MESSAGE = (
    "Недостаточно быстрых рецептов для разнообразного плана. "
    "Увеличьте максимальное время приготовления или разрешите приготовление на 2 дня."
)
FAVORITES_ONLY_FRIENDLY_MESSAGE = (
    "Недостаточно избранных рецептов для формирования разнообразного плана. "
    "Разрешите использовать все рецепты или добавьте больше рецептов в избранное."
)
EXCLUSIONS_TOO_STRICT_FRIENDLY_MESSAGE = (
    "Недостаточно рецептов с учётом исключённых продуктов и категорий. "
    "Ослабьте ограничения или добавьте больше подходящих рецептов."
)
DIVERSITY_PRECHECK_MEAL_TYPES = ("lunch", "dinner")
MONTHS_RU_GENITIVE = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


class PlanAutogenerateNotEnoughRecipesError(ValueError):
    pass


class PlanAutogeneratePlanNotFoundError(ValueError):
    pass


class PlanAutogenerateSlotNotFoundError(ValueError):
    pass


class PlanAutogenerateDayOutOfRangeError(ValueError):
    pass


class PlanAutogenerateProfileNotFoundError(ValueError):
    pass


class PlanAutogenerateProfileValidationError(ValueError):
    pass


class PlanAutogenerateLowFeasibilityError(ValueError):
    pass


def _map_not_enough_recipes_message(*, detail: str, has_generalized_exclusions: bool) -> str:
    if not has_generalized_exclusions:
        return detail
    if detail in {DIVERSITY_PRECHECK_FRIENDLY_MESSAGE, FAVORITES_ONLY_FRIENDLY_MESSAGE}:
        return detail
    return EXCLUSIONS_TOO_STRICT_FRIENDLY_MESSAGE


def get_slot_templates(meals_per_day: int) -> tuple[SlotTemplate, ...]:
    templates = SLOT_TEMPLATES_BY_MEALS_PER_DAY.get(meals_per_day)
    if templates is None:
        raise ValueError("Unsupported meals_per_day")
    return templates


def get_meal_type_sequence(meals_per_day: int) -> list[str]:
    return [template.meal_type for template in get_slot_templates(meals_per_day)]


def _candidate_multipliers(*, extra_candidates: list[Decimal] | None = None) -> tuple[Decimal, ...]:
    values = set(SERVINGS_MULTIPLIER_CANDIDATES)
    for value in extra_candidates or []:
        if value > 0:
            values.add(value)
    return tuple(sorted(values))


def _normalize_target(value: int | None) -> Decimal | None:
    if value is None or value <= 0:
        return None
    return Decimal(value)


def _build_plan_targets(
    *,
    kcal: int | None,
    protein: int | None,
    fat: int | None,
    carbs: int | None,
    fiber: int | None,
) -> PlanTargets:
    return PlanTargets(
        kcal=_normalize_target(kcal),
        protein=_normalize_target(protein),
        fat=_normalize_target(fat),
        carbs=_normalize_target(carbs),
        fiber=_normalize_target(fiber),
    )


def _build_autogenerated_plan_title(*, start_date: date, custom_title: str | None) -> str:
    normalized = custom_title.strip() if custom_title is not None else ""
    if normalized:
        return normalized
    month_label = MONTHS_RU_GENITIVE.get(start_date.month)
    if month_label is None:
        month_label = str(start_date.month)
    return f"План с {start_date.day} {month_label} {start_date.year} г."


def _resolve_profile_for_autogenerate(
    db: Session,
    *,
    user_id: int,
    profile_id: int | None,
) -> Profile:
    if profile_id is not None:
        profile = db.execute(
            select(Profile)
            .where(
                Profile.id == profile_id,
                Profile.user_id == user_id,
            )
            .options(
                selectinload(Profile.excluded_food_links),
                selectinload(Profile.preferred_food_links),
            )
        ).scalar_one_or_none()
        if profile is None:
            raise PlanAutogenerateProfileNotFoundError("Profile not found")
        return profile

    profile = db.execute(
        select(Profile)
        .where(Profile.user_id == user_id)
        .options(
            selectinload(Profile.excluded_food_links),
            selectinload(Profile.preferred_food_links),
        )
        .order_by(Profile.id.asc())
        .limit(1)
    ).scalar_one_or_none()
    if profile is None:
        raise PlanAutogenerateProfileValidationError(
            "Profile is required for autogenerate. Create one or pass profile_id."
        )
    return profile


def _resolve_targets_from_profile(profile: Profile) -> PlanTargets:
    targets = _build_plan_targets(
        kcal=profile.target_kcal,
        protein=profile.target_protein,
        fat=profile.target_fat,
        carbs=profile.target_carbs,
        fiber=profile.target_fiber,
    )
    if targets.kcal is None:
        raise PlanAutogenerateProfileValidationError(
            "Selected profile must have target_kcal > 0 for autogeneration."
        )
    return targets


def _resolve_targets_from_plan(plan: Plan) -> PlanTargets:
    return _build_plan_targets(
        kcal=plan.target_kcal,
        protein=plan.target_protein,
        fat=plan.target_fat,
        carbs=plan.target_carbs,
        fiber=plan.target_fiber,
    )


def select_profile_targets(
    db: Session,
    *,
    user_id: int,
    profile_id: int | None,
) -> tuple[Profile, PlanTargets]:
    """Resolve planning targets from a selected profile for new plan generation."""
    selected_profile = _resolve_profile_for_autogenerate(
        db,
        user_id=user_id,
        profile_id=profile_id,
    )
    return selected_profile, _resolve_targets_from_profile(selected_profile)


def select_plan_snapshot_targets(plan: Plan) -> PlanTargets:
    """Read immutable target snapshot from an already created plan."""
    return _resolve_targets_from_plan(plan)


def _normalized_batch_cooking_config(batch_cooking: object | None) -> dict[str, int]:
    if batch_cooking is None:
        return {}

    config: dict[str, int] = {}
    for meal_type in ("breakfast", "lunch", "dinner", "snack"):
        value = getattr(batch_cooking, meal_type, None)
        if value is None:
            continue
        config[meal_type] = int(value)
    return config


def build_autoplan_preferences(
    db: Session,
    *,
    user_id: int,
    profile: Profile,
    payload: PlanAutogenerateRequest | None,
) -> AutoplanPreferences:
    profile_excluded = set(profile.excluded_food_ids)
    profile_excluded_categories = {
        value.strip() for value in profile.excluded_categories if value and value.strip()
    }
    profile_excluded_terms = {
        value.strip().casefold() for value in profile.excluded_terms if value and value.strip()
    }
    profile_preferred = set(profile.preferred_food_ids)
    profile_categories = {value.strip() for value in profile.preferred_categories if value and value.strip()}

    payload_excluded = set(payload.excluded_food_ids if payload is not None else [])
    max_cook_time = (
        payload.max_cook_time_minutes
        if payload is not None and payload.max_cook_time_minutes is not None
        else profile.max_cook_time_minutes
    )
    batch_cooking = _normalized_batch_cooking_config(payload.batch_cooking if payload is not None else None)
    favorite_mode = payload.favorite_recipes_mode if payload is not None else "none"
    favorite_recipe_ids = (
        list_favorite_recipe_ids(db, user_id=user_id)
        if favorite_mode in {"prefer", "only"}
        else set()
    )

    return AutoplanPreferences(
        excluded_food_ids=profile_excluded.union(payload_excluded),
        excluded_categories=profile_excluded_categories,
        excluded_terms=profile_excluded_terms,
        preferred_food_ids=profile_preferred,
        preferred_categories=profile_categories,
        favorite_recipe_ids=favorite_recipe_ids,
        favorite_recipes_mode=favorite_mode,
        max_cook_time_minutes=max_cook_time,
        batch_cooking=batch_cooking,
    )


def build_plan_preferences_for_slot_operations(
    *,
    profile: Profile | None,
    payload_excluded_food_ids: list[int],
    payload_max_cook_time_minutes: int | None = None,
) -> AutoplanPreferences:
    resolved_max_cook_time = payload_max_cook_time_minutes
    if profile is None:
        return AutoplanPreferences(
            excluded_food_ids=set(payload_excluded_food_ids),
            excluded_categories=set(),
            excluded_terms=set(),
            preferred_food_ids=set(),
            preferred_categories=set(),
            favorite_recipe_ids=set(),
            favorite_recipes_mode="none",
            max_cook_time_minutes=resolved_max_cook_time,
            batch_cooking={},
        )

    if resolved_max_cook_time is None:
        resolved_max_cook_time = profile.max_cook_time_minutes

    return AutoplanPreferences(
        excluded_food_ids=set(profile.excluded_food_ids).union(payload_excluded_food_ids),
        excluded_categories={value.strip() for value in profile.excluded_categories if value and value.strip()},
        excluded_terms={value.strip().casefold() for value in profile.excluded_terms if value and value.strip()},
        preferred_food_ids=set(profile.preferred_food_ids),
        preferred_categories={value.strip() for value in profile.preferred_categories if value and value.strip()},
        favorite_recipe_ids=set(),
        favorite_recipes_mode="none",
        max_cook_time_minutes=resolved_max_cook_time,
        batch_cooking={},
    )


def _normalize_recipe_meal_types(recipe: Recipe) -> set[str]:
    return {value.strip().lower() for value in recipe.meal_types}


def _recipe_name_tokens(value: str) -> set[str]:
    normalized = re.sub(r"[^\w\s]", " ", value.casefold(), flags=re.UNICODE)
    return {token for token in normalized.split() if token}


def recipe_name_similarity(left_name: str, right_name: str) -> Decimal:
    left_tokens = _recipe_name_tokens(left_name)
    right_tokens = _recipe_name_tokens(right_name)
    if not left_tokens or not right_tokens:
        return Decimal("0")

    intersection_size = len(left_tokens & right_tokens)
    union_size = len(left_tokens | right_tokens)
    if union_size == 0:
        return Decimal("0")
    return Decimal(intersection_size) / Decimal(union_size)


def _recipe_name_similarity_penalty(*, recipe_name: str, reference_recipe_names: list[str] | None) -> Decimal:
    if not reference_recipe_names:
        return Decimal("0")

    max_similarity = Decimal("0")
    for reference_name in reference_recipe_names:
        similarity = recipe_name_similarity(recipe_name, reference_name)
        if similarity > max_similarity:
            max_similarity = similarity

    if max_similarity < RECIPE_NAME_SIMILARITY_THRESHOLD:
        return Decimal("0")
    return RECIPE_NAME_SIMILARITY_PENALTY


def _load_accessible_recipes(
    db: Session,
    *,
    user_id: int,
    use_public_recipes: bool,
) -> list[Recipe]:
    stmt = (
        select(Recipe)
        .options(selectinload(Recipe.ingredients).selectinload(RecipeIngredient.food))
        .where(
            build_accessible_recipes_condition(
                user_id=user_id,
                include_public=use_public_recipes,
            )
        )
        .order_by(Recipe.id.asc())
    )
    return db.execute(stmt).scalars().all()


def _build_food_search_text(recipe: Recipe, *, ingredient_index: int) -> str:
    ingredient = recipe.ingredients[ingredient_index]
    if ingredient.food is None:
        return ""
    name = ingredient.food.name or ""
    brand = ingredient.food.brand or ""
    combined = f"{name} {brand}".strip()
    return combined.casefold()


def _recipe_has_excluded_ingredient(
    *,
    recipe: Recipe,
    excluded_food_ids: set[int],
    excluded_categories: set[str],
    excluded_terms: set[str],
) -> bool:
    for index, ingredient in enumerate(recipe.ingredients):
        if ingredient.food_id in excluded_food_ids:
            return True
        if ingredient.food is None:
            continue

        if excluded_categories:
            category = (ingredient.food.category or "").strip()
            if category and category in excluded_categories:
                return True

        if excluded_terms:
            searchable = _build_food_search_text(recipe, ingredient_index=index)
            if searchable and any(term in searchable for term in excluded_terms):
                return True

    return False


def filter_candidates(
    *,
    candidates: list[Recipe],
    expected_meal_type: str,
    excluded_recipe_ids: list[int] | set[int],
    excluded_food_ids: list[int] | set[int],
    excluded_categories: list[str] | set[str] | None = None,
    excluded_terms: list[str] | set[str] | None = None,
    max_cook_time_minutes: int | None = None,
    avoid_recipe_ids: set[int] | None = None,
) -> list[Recipe]:
    """
    Constraint layer: leave only candidates that satisfy hard rules for a slot.
    """
    expected_meal_type_normalized = expected_meal_type.strip().lower()
    excluded_recipe_ids_set = set(excluded_recipe_ids)
    excluded_food_ids_set = set(excluded_food_ids)
    excluded_categories_set = {value.strip() for value in (excluded_categories or []) if value and value.strip()}
    excluded_terms_set = {value.strip().casefold() for value in (excluded_terms or []) if value and value.strip()}
    avoid_recipe_ids_set = avoid_recipe_ids or set()

    filtered_candidates: list[Recipe] = []
    for recipe in sorted(candidates, key=lambda value: value.id):
        if recipe.id in excluded_recipe_ids_set:
            continue
        if recipe.id in avoid_recipe_ids_set:
            continue
        if expected_meal_type_normalized not in _normalize_recipe_meal_types(recipe):
            continue
        if excluded_food_ids_set or excluded_categories_set or excluded_terms_set:
            if _recipe_has_excluded_ingredient(
                recipe=recipe,
                excluded_food_ids=excluded_food_ids_set,
                excluded_categories=excluded_categories_set,
                excluded_terms=excluded_terms_set,
            ):
                continue
        if (
            max_cook_time_minutes is not None
            and recipe.cook_time_minutes is not None
            and recipe.cook_time_minutes > max_cook_time_minutes
        ):
            continue
        filtered_candidates.append(recipe)
    return filtered_candidates


def get_accessible_recipe_candidates(
    db: Session,
    *,
    user_id: int,
    meal_type: str,
    use_public_recipes: bool,
    excluded_recipe_ids: list[int],
    excluded_food_ids: list[int],
    excluded_categories: list[str] | None = None,
    excluded_terms: list[str] | None = None,
    max_cook_time_minutes: int | None = None,
) -> list[Recipe]:
    accessible_recipes = _load_accessible_recipes(
        db,
        user_id=user_id,
        use_public_recipes=use_public_recipes,
    )
    return filter_candidates(
        candidates=accessible_recipes,
        expected_meal_type=meal_type,
        excluded_recipe_ids=excluded_recipe_ids,
        excluded_food_ids=excluded_food_ids,
        excluded_categories=excluded_categories,
        excluded_terms=excluded_terms,
        max_cook_time_minutes=max_cook_time_minutes,
    )


def _raise_not_enough_recipes_error(*, meal_type: str, day_date: date) -> None:
    raise PlanAutogenerateNotEnoughRecipesError(
        f"Not enough recipes for meal_type={meal_type} on {day_date.isoformat()}"
    )


def _load_plan_with_slots_for_user(db: Session, *, user_id: int, plan_id: int) -> Plan:
    plan = db.execute(
        select(Plan)
        .where(Plan.id == plan_id, Plan.owner_user_id == user_id)
        .options(
            selectinload(Plan.profile).selectinload(Profile.excluded_food_links),
            selectinload(Plan.profile).selectinload(Profile.preferred_food_links),
            selectinload(Plan.slots)
            .selectinload(PlanSlot.recipe)
            .selectinload(Recipe.ingredients)
            .selectinload(RecipeIngredient.food),
            selectinload(Plan.slots)
            .selectinload(PlanSlot.ingredient_overrides)
            .selectinload(PlanSlotIngredientOverride.food),
        )
    ).scalar_one_or_none()
    if plan is None:
        raise PlanAutogeneratePlanNotFoundError("Plan not found")
    return plan


def _resolve_slot_template(*, meals_per_day: int, slot_index: int) -> SlotTemplate:
    templates = get_slot_templates(meals_per_day)
    if slot_index < 0 or slot_index >= len(templates):
        raise ValueError("Unsupported slot_index")
    return templates[slot_index]


def _build_recipe_usage_counts(
    *,
    slots: list[PlanSlot],
    excluded_slot_ids: set[int] | None = None,
) -> dict[int, int]:
    usage_counts: dict[int, int] = defaultdict(int)
    excluded_ids = excluded_slot_ids or set()
    for slot in slots:
        if slot.id in excluded_ids or slot.recipe_id is None:
            continue
        usage_counts[slot.recipe_id] += 1
    return usage_counts


def _build_slot_recipe_dates(
    *,
    slots: list[PlanSlot],
    excluded_slot_ids: set[int] | None = None,
) -> dict[int, dict[int, list[date]]]:
    grouped: dict[int, dict[int, list[date]]] = defaultdict(lambda: defaultdict(list))
    excluded_ids = excluded_slot_ids or set()
    for slot in slots:
        if slot.id in excluded_ids or slot.recipe_id is None:
            continue
        grouped[slot.slot_index][slot.recipe_id].append(slot.day_date)

    for by_recipe in grouped.values():
        for recipe_dates in by_recipe.values():
            recipe_dates.sort()
    return grouped


def _build_recipe_lookup(*, slots: list[PlanSlot], extra_recipes: list[Recipe] | None = None) -> dict[int, Recipe]:
    lookup: dict[int, Recipe] = {}
    for slot in slots:
        if slot.recipe_id is None or slot.recipe is None:
            continue
        lookup[slot.recipe_id] = slot.recipe

    for recipe in extra_recipes or []:
        lookup[recipe.id] = recipe
    return lookup


def _zero_totals() -> dict[str, Decimal]:
    return {
        "kcal": Decimal("0"),
        "protein": Decimal("0"),
        "fat": Decimal("0"),
        "carbs": Decimal("0"),
        "fiber": Decimal("0"),
    }


def _add_totals(
    totals: dict[str, Decimal],
    *,
    nutrients: dict[str, Decimal],
    servings_multiplier: Decimal,
) -> None:
    totals["kcal"] += nutrients["kcal"] * servings_multiplier
    totals["protein"] += nutrients["protein"] * servings_multiplier
    totals["fat"] += nutrients["fat"] * servings_multiplier
    totals["carbs"] += nutrients["carbs"] * servings_multiplier
    totals["fiber"] += nutrients["fiber"] * servings_multiplier


def _calculate_day_totals(
    *,
    day_slots: list[PlanSlot],
    selected_slot_candidate_by_slot_id: dict[int, tuple[int, Decimal]] | None,
    recipe_by_id: dict[int, Recipe],
    recipe_nutrients_cache: dict[int, dict[str, Decimal]],
) -> dict[str, Decimal]:
    totals = _zero_totals()
    selected_by_slot_id = selected_slot_candidate_by_slot_id or {}

    for slot in day_slots:
        if slot.id in selected_by_slot_id:
            recipe_id, servings_multiplier = selected_by_slot_id[slot.id]
        else:
            recipe_id = slot.recipe_id
            servings_multiplier = slot.servings_multiplier

        if recipe_id is None:
            continue
        recipe = recipe_by_id.get(recipe_id)
        if recipe is None:
            continue

        nutrients = _recipe_nutrients_per_serving(
            recipe,
            recipe_nutrients_cache=recipe_nutrients_cache,
        )
        _add_totals(
            totals,
            nutrients=nutrients,
            servings_multiplier=servings_multiplier,
        )

    return totals


def _recipe_nutrients_per_serving(
    recipe: Recipe,
    *,
    recipe_nutrients_cache: dict[int, dict[str, Decimal]],
) -> dict[str, Decimal]:
    cached = recipe_nutrients_cache.get(recipe.id)
    if cached is not None:
        return cached

    nutrients = calculate_recipe_nutrients(recipe)
    normalized = {
        "kcal": nutrients["per_serving_kcal"],
        "protein": nutrients["per_serving_protein"],
        "fat": nutrients["per_serving_fat"],
        "carbs": nutrients["per_serving_carbs"],
        "fiber": nutrients["per_serving_fiber"],
    }
    recipe_nutrients_cache[recipe.id] = normalized
    return normalized


def _calculate_day_totals_before_slot(
    *,
    day_slots: list[PlanSlot],
    target_slot_index: int,
    selected_slot_candidate_by_slot_id: dict[int, tuple[int, Decimal]],
    recipe_by_id: dict[int, Recipe],
    recipe_nutrients_cache: dict[int, dict[str, Decimal]],
) -> dict[str, Decimal]:
    totals = _zero_totals()
    for slot in day_slots:
        if slot.slot_index >= target_slot_index:
            continue

        if slot.id in selected_slot_candidate_by_slot_id:
            recipe_id, servings_multiplier = selected_slot_candidate_by_slot_id[slot.id]
        else:
            recipe_id = slot.recipe_id
            servings_multiplier = slot.servings_multiplier

        if recipe_id is None:
            continue

        recipe = recipe_by_id.get(recipe_id)
        if recipe is None:
            continue

        nutrients = _recipe_nutrients_per_serving(recipe, recipe_nutrients_cache=recipe_nutrients_cache)
        _add_totals(totals, nutrients=nutrients, servings_multiplier=servings_multiplier)
    return totals


def _relative_penalty(actual: Decimal, expected: Decimal | None, *, weight: Decimal) -> Decimal:
    if expected is None or expected <= 0:
        return Decimal("0")
    return (abs(actual - expected) / expected) * weight


def _overshoot_ratio(actual: Decimal, target: Decimal | None) -> Decimal:
    if target is None or target <= 0:
        return Decimal("0")
    if actual <= target:
        return Decimal("0")
    return (actual - target) / target


def _undershoot_ratio(actual: Decimal, target: Decimal | None) -> Decimal:
    if target is None or target <= 0:
        return Decimal("0")
    if actual >= target:
        return Decimal("0")
    return (target - actual) / target


def _piecewise_penalty(
    ratio: Decimal,
    *,
    weight: Decimal,
    mild_ratio: Decimal = Decimal("0.10"),
    sharp_ratio: Decimal = Decimal("0.25"),
) -> Decimal:
    if ratio <= 0:
        return Decimal("0")

    mild_part = min(ratio, mild_ratio)
    penalty = mild_part * weight

    if ratio > mild_ratio:
        moderate_part = min(ratio, sharp_ratio) - mild_ratio
        penalty += moderate_part * weight * Decimal("2.5")

    if ratio > sharp_ratio:
        severe_part = ratio - sharp_ratio
        penalty += severe_part * weight * Decimal("4.0")

    return penalty


def _day_totals_score(*, totals: dict[str, Decimal], targets: PlanTargets) -> Decimal:
    score = Decimal("0")
    score += _relative_penalty(totals["kcal"], targets.kcal, weight=DAY_VARIATION_SCORE_WEIGHT)
    score += _relative_penalty(totals["protein"], targets.protein, weight=DAY_VARIATION_SCORE_WEIGHT * Decimal("0.65"))
    score += _piecewise_penalty(
        _overshoot_ratio(totals["fat"], targets.fat),
        weight=DAY_VARIATION_SCORE_WEIGHT * Decimal("1.15"),
        mild_ratio=Decimal("0.08"),
        sharp_ratio=Decimal("0.20"),
    )
    score += _piecewise_penalty(
        _undershoot_ratio(totals["carbs"], targets.carbs),
        weight=DAY_VARIATION_SCORE_WEIGHT * Decimal("1.05"),
        mild_ratio=Decimal("0.08"),
        sharp_ratio=Decimal("0.22"),
    )
    score += _piecewise_penalty(
        _undershoot_ratio(totals["fiber"], targets.fiber),
        weight=DAY_VARIATION_SCORE_WEIGHT * Decimal("0.35"),
        mild_ratio=Decimal("0.10"),
        sharp_ratio=Decimal("0.28"),
    )
    return score


def _is_day_variation_acceptable(
    *,
    baseline_totals: dict[str, Decimal],
    candidate_totals: dict[str, Decimal],
    targets: PlanTargets,
) -> bool:
    baseline_score = _day_totals_score(totals=baseline_totals, targets=targets)
    candidate_score = _day_totals_score(totals=candidate_totals, targets=targets)
    allowed_score = max(
        baseline_score * DAY_VARIATION_WORSENING_FACTOR,
        baseline_score + DAY_VARIATION_WORSENING_MARGIN,
    )
    if candidate_score > allowed_score:
        return False

    if targets.kcal is not None and targets.kcal > 0:
        baseline_kcal_error = abs(baseline_totals["kcal"] - targets.kcal)
        candidate_kcal_error = abs(candidate_totals["kcal"] - targets.kcal)
        allowed_kcal_error = baseline_kcal_error + (targets.kcal * DAY_VARIATION_KCAL_WORSENING_RATIO)
        if candidate_kcal_error > allowed_kcal_error:
            return False

    return True


def _day_pattern_repeat_penalty(
    *,
    slot_index: int,
    candidate_recipe_id: int,
    meals_per_day: int,
    current_day_selected_recipe_ids_by_slot_index: dict[int, int] | None,
    historical_day_patterns: set[tuple[int, ...]] | None,
) -> Decimal:
    if not historical_day_patterns or not current_day_selected_recipe_ids_by_slot_index:
        return Decimal("0")

    penalty = Decimal("0")
    prefix_recipe_ids: list[int] = []
    for idx in range(slot_index + 1):
        if idx == slot_index:
            prefix_recipe_ids.append(candidate_recipe_id)
            continue
        selected_recipe_id = current_day_selected_recipe_ids_by_slot_index.get(idx)
        if selected_recipe_id is None:
            return Decimal("0")
        prefix_recipe_ids.append(selected_recipe_id)

    for pattern in historical_day_patterns:
        if len(pattern) != meals_per_day:
            continue
        if all(pattern[idx] == prefix_recipe_ids[idx] for idx in range(slot_index + 1)):
            if slot_index == meals_per_day - 1:
                penalty += DAY_PATTERN_EXACT_REPEAT_PENALTY
            else:
                penalty += DAY_PATTERN_PREFIX_PENALTY * Decimal(slot_index + 1)

    return penalty


def _macro_energy_shares(nutrients: dict[str, Decimal]) -> tuple[Decimal, Decimal, Decimal]:
    protein_energy = nutrients["protein"] * Decimal("4")
    fat_energy = nutrients["fat"] * Decimal("9")
    carbs_energy = nutrients["carbs"] * Decimal("4")
    total_energy = protein_energy + fat_energy + carbs_energy
    if total_energy <= 0:
        return Decimal("0"), Decimal("0"), Decimal("0")
    return (
        protein_energy / total_energy,
        fat_energy / total_energy,
        carbs_energy / total_energy,
    )


def is_protein_heavy(nutrients: dict[str, Decimal]) -> bool:
    protein_share, _fat_share, carbs_share = _macro_energy_shares(nutrients)
    return protein_share >= Decimal("0.34") and carbs_share <= Decimal("0.35")


def is_carb_heavy(nutrients: dict[str, Decimal]) -> bool:
    _protein_share, _fat_share, carbs_share = _macro_energy_shares(nutrients)
    return carbs_share >= Decimal("0.48")


def is_fat_heavy(nutrients: dict[str, Decimal]) -> bool:
    _protein_share, fat_share, _carbs_share = _macro_energy_shares(nutrients)
    return fat_share >= Decimal("0.42")


def is_fat_friendly(nutrients: dict[str, Decimal]) -> bool:
    _protein_share, fat_share, _carbs_share = _macro_energy_shares(nutrients)
    return fat_share >= FAT_FRIENDLY_SHARE_THRESHOLD and nutrients["fat"] >= FAT_FRIENDLY_FAT_GRAMS_THRESHOLD


def is_dry_low_fat_candidate(nutrients: dict[str, Decimal]) -> bool:
    protein_share, fat_share, _carbs_share = _macro_energy_shares(nutrients)
    return fat_share <= DRY_LOW_FAT_SHARE_THRESHOLD and nutrients["fat"] <= Decimal("8") and protein_share >= Decimal("0.26")


def is_balanced_macro_profile(nutrients: dict[str, Decimal]) -> bool:
    protein_share, fat_share, carbs_share = _macro_energy_shares(nutrients)
    return (
        Decimal("0.18") <= protein_share <= Decimal("0.35")
        and Decimal("0.20") <= fat_share <= Decimal("0.40")
        and Decimal("0.30") <= carbs_share <= Decimal("0.60")
    )


def _max_multiplier_for_recipe(nutrients: dict[str, Decimal]) -> Decimal:
    if nutrients["protein"] >= PROTEIN_DENSE_PER_SERVING_THRESHOLD:
        return PROTEIN_DENSE_MULTIPLIER_CAP
    if is_protein_heavy(nutrients) and nutrients["carbs"] <= LOW_CARB_PER_SERVING_THRESHOLD:
        return PROTEIN_DENSE_MULTIPLIER_CAP
    return max(SERVINGS_MULTIPLIER_CANDIDATES)


def _slot_target_kcal(*, targets: PlanTargets, slot_weight: Decimal) -> Decimal | None:
    if targets.kcal is None or targets.kcal <= 0:
        return None
    return targets.kcal * slot_weight


def _slot_target_cap_ratio(*, meals_per_day: int, expected_meal_type: str) -> Decimal:
    if expected_meal_type == "snack":
        if meals_per_day >= 5:
            return SNACK_SLOT_TARGET_CAP_RATIO_5_PLUS
        return SNACK_SLOT_TARGET_CAP_RATIO_DEFAULT
    if expected_meal_type == "breakfast":
        if meals_per_day >= 5:
            return BREAKFAST_SLOT_TARGET_CAP_RATIO_5_PLUS
        return BREAKFAST_SLOT_TARGET_CAP_RATIO_DEFAULT
    return MAIN_SLOT_TARGET_CAP_RATIO


def is_candidate_reasonable_for_slot(
    *,
    nutrients: dict[str, Decimal],
    servings_multiplier: Decimal,
    slot_weight: Decimal,
    meals_per_day: int,
    expected_meal_type: str,
    targets: PlanTargets,
) -> bool:
    slot_target_kcal = _slot_target_kcal(targets=targets, slot_weight=slot_weight)
    if slot_target_kcal is None or slot_target_kcal <= 0:
        return True

    projected_slot_kcal = nutrients["kcal"] * servings_multiplier
    slot_cap_ratio = _slot_target_cap_ratio(
        meals_per_day=meals_per_day,
        expected_meal_type=expected_meal_type,
    )
    return projected_slot_kcal <= slot_target_kcal * slot_cap_ratio


def slot_guardrail_penalty(
    *,
    nutrients: dict[str, Decimal],
    servings_multiplier: Decimal,
    slot_weight: Decimal,
    meals_per_day: int,
    expected_meal_type: str,
    targets: PlanTargets,
) -> Decimal:
    slot_target_kcal = _slot_target_kcal(targets=targets, slot_weight=slot_weight)
    if slot_target_kcal is None or slot_target_kcal <= 0:
        return Decimal("0")

    projected_slot_kcal = nutrients["kcal"] * servings_multiplier
    cap_ratio = _slot_target_cap_ratio(
        meals_per_day=meals_per_day,
        expected_meal_type=expected_meal_type,
    )
    cap_kcal = slot_target_kcal * cap_ratio
    if projected_slot_kcal <= cap_kcal:
        return Decimal("0")

    overshoot_ratio = (projected_slot_kcal - cap_kcal) / cap_kcal
    meal_type_weight_factor = Decimal("1.0")
    if expected_meal_type in {"snack", "breakfast"} and meals_per_day >= 5:
        meal_type_weight_factor = Decimal("1.35")

    return _piecewise_penalty(
        overshoot_ratio,
        weight=SLOT_GUARDRAIL_PENALTY_WEIGHT * meal_type_weight_factor,
        mild_ratio=Decimal("0.08"),
        sharp_ratio=Decimal("0.24"),
    )


def _feasibility_gap_ratio(*, target: Decimal | None, reachable_max: Decimal) -> Decimal:
    if target is None or target <= 0:
        return Decimal("0")
    if reachable_max >= target:
        return Decimal("0")
    return (target - reachable_max) / target


def _estimate_daily_feasibility(
    *,
    slot_templates: tuple[SlotTemplate, ...],
    candidates_by_meal_type: dict[str, list[Recipe]],
    recipe_nutrients_cache: dict[int, dict[str, Decimal]],
) -> FeasibilityEstimate:
    per_meal_type_max: dict[str, dict[str, Decimal]] = {}
    for meal_type in {template.meal_type for template in slot_templates}:
        candidates = candidates_by_meal_type.get(meal_type, [])
        max_values = _zero_totals()
        for recipe in candidates:
            nutrients = _recipe_nutrients_per_serving(recipe, recipe_nutrients_cache=recipe_nutrients_cache)
            max_multiplier = _max_multiplier_for_recipe(nutrients)
            max_values["kcal"] = max(max_values["kcal"], nutrients["kcal"] * max_multiplier)
            max_values["protein"] = max(max_values["protein"], nutrients["protein"] * max_multiplier)
            max_values["fat"] = max(max_values["fat"], nutrients["fat"] * max_multiplier)
            max_values["carbs"] = max(max_values["carbs"], nutrients["carbs"] * max_multiplier)
            max_values["fiber"] = max(max_values["fiber"], nutrients["fiber"] * max_multiplier)
        per_meal_type_max[meal_type] = max_values

    max_day = _zero_totals()
    for template in slot_templates:
        slot_max = per_meal_type_max.get(template.meal_type, _zero_totals())
        max_day["kcal"] += slot_max["kcal"]
        max_day["protein"] += slot_max["protein"]
        max_day["fat"] += slot_max["fat"]
        max_day["carbs"] += slot_max["carbs"]
        max_day["fiber"] += slot_max["fiber"]

    return FeasibilityEstimate(
        max_daily_kcal=max_day["kcal"],
        max_daily_protein=max_day["protein"],
        max_daily_fat=max_day["fat"],
        max_daily_carbs=max_day["carbs"],
        max_daily_fiber=max_day["fiber"],
    )


def _build_low_feasibility_message(
    *,
    meals_per_day: int,
    targets: PlanTargets,
    estimate: FeasibilityEstimate,
) -> str:
    target_kcal = int(targets.kcal or 0)
    reachable_kcal = int(estimate.max_daily_kcal)

    message_parts = [
        (
            f"Для этой цели и {meals_per_day} приемов пищи доступных блюд недостаточно: "
            f"реалистичный максимум около {reachable_kcal} ккал/день при цели {target_kcal} ккал."
        )
    ]
    if meals_per_day <= 3 and (targets.kcal or Decimal("0")) >= HIGH_TARGET_KCAL_RISK_THRESHOLD:
        message_parts.append("Для целей 3200+ ккал обычно нужны 4-5 приемов пищи.")
    message_parts.append("Попробуйте 4-5 приемов пищи или расширьте базу рецептов.")
    return " ".join(message_parts)


def _recommended_candidates_for_batch(
    *,
    days_count: int,
    batch_days: int,
) -> int:
    if batch_days <= 1:
        return min(days_count, 4)
    if batch_days == 2:
        return 3 if days_count >= 5 else 2
    return 2


def _ensure_autogenerate_diversity_feasibility(
    *,
    days_count: int,
    slot_templates: tuple[SlotTemplate, ...],
    candidates_by_meal_type: dict[str, list[Recipe]],
    batch_cooking: dict[str, int],
    max_cook_time_minutes: int | None,
) -> None:
    if max_cook_time_minutes is None:
        return

    meal_types_in_plan = {template.meal_type for template in slot_templates}
    for meal_type in DIVERSITY_PRECHECK_MEAL_TYPES:
        if meal_type not in meal_types_in_plan:
            continue
        candidate_count = len(candidates_by_meal_type.get(meal_type, []))
        batch_days = int(batch_cooking.get(meal_type, 1))
        recommended_count = _recommended_candidates_for_batch(
            days_count=days_count,
            batch_days=batch_days,
        )
        if candidate_count < recommended_count:
            raise PlanAutogenerateNotEnoughRecipesError(DIVERSITY_PRECHECK_FRIENDLY_MESSAGE)


def _ensure_autogenerate_feasibility(
    *,
    meals_per_day: int,
    slot_templates: tuple[SlotTemplate, ...],
    targets: PlanTargets,
    candidates_by_meal_type: dict[str, list[Recipe]],
    recipe_nutrients_cache: dict[int, dict[str, Decimal]],
) -> None:
    if targets.kcal is None or targets.kcal <= 0:
        return

    # MVP guardrail: trigger feasibility precheck only for genuinely high-calorie profiles.
    if targets.kcal < HIGH_TARGET_KCAL_RISK_THRESHOLD:
        return

    if any(not candidates_by_meal_type.get(template.meal_type) for template in slot_templates):
        return

    estimate = _estimate_daily_feasibility(
        slot_templates=slot_templates,
        candidates_by_meal_type=candidates_by_meal_type,
        recipe_nutrients_cache=recipe_nutrients_cache,
    )

    kcal_gap_ratio = _feasibility_gap_ratio(target=targets.kcal, reachable_max=estimate.max_daily_kcal)
    carbs_gap_ratio = _feasibility_gap_ratio(target=targets.carbs, reachable_max=estimate.max_daily_carbs)
    fat_gap_ratio = _feasibility_gap_ratio(target=targets.fat, reachable_max=estimate.max_daily_fat)

    low_feasibility = kcal_gap_ratio > LOW_FEASIBILITY_KCAL_GAP_RATIO
    if (
        (targets.kcal or Decimal("0")) >= HIGH_TARGET_KCAL_RISK_THRESHOLD
        and meals_per_day <= 3
        and (carbs_gap_ratio > LOW_FEASIBILITY_CARBS_GAP_RATIO or fat_gap_ratio > LOW_FEASIBILITY_FAT_GAP_RATIO)
    ):
        low_feasibility = True

    if not low_feasibility:
        return

    raise PlanAutogenerateLowFeasibilityError(
        _build_low_feasibility_message(
            meals_per_day=meals_per_day,
            targets=targets,
            estimate=estimate,
        )
    )


def run_feasibility_check(
    *,
    days_count: int,
    meals_per_day: int,
    slot_templates: tuple[SlotTemplate, ...],
    targets: PlanTargets,
    candidates_by_meal_type: dict[str, list[Recipe]],
    recipe_nutrients_cache: dict[int, dict[str, Decimal]],
    batch_cooking: dict[str, int],
    max_cook_time_minutes: int | None,
) -> None:
    """Precheck high-calorie scenarios before generating slots."""
    _ensure_autogenerate_diversity_feasibility(
        days_count=days_count,
        slot_templates=slot_templates,
        candidates_by_meal_type=candidates_by_meal_type,
        batch_cooking=batch_cooking,
        max_cook_time_minutes=max_cook_time_minutes,
    )
    _ensure_autogenerate_feasibility(
        meals_per_day=meals_per_day,
        slot_templates=slot_templates,
        targets=targets,
        candidates_by_meal_type=candidates_by_meal_type,
        recipe_nutrients_cache=recipe_nutrients_cache,
    )


def _cumulative_weight_for_slot(*, meals_per_day: int, slot_index: int) -> Decimal:
    templates = get_slot_templates(meals_per_day)
    return sum(template.weight for template in templates[: slot_index + 1])


def _calculate_repeat_penalty(
    *,
    recipe_id: int,
    slot_index: int,
    day_date: date,
    recipe_usage_counts: dict[int, int],
    slot_recipe_dates: dict[int, dict[int, list[date]]],
) -> Decimal:
    penalty = Decimal(recipe_usage_counts.get(recipe_id, 0)) * REPEAT_USAGE_PENALTY

    same_slot_dates = slot_recipe_dates.get(slot_index, {}).get(recipe_id, [])
    for existing_day in same_slot_dates:
        distance = abs((day_date - existing_day).days)
        if distance == 0:
            continue
        if distance in REPEAT_SAME_SLOT_BY_DISTANCE:
            penalty += REPEAT_SAME_SLOT_BY_DISTANCE[distance]
        elif distance <= 7:
            penalty += FAR_REPEAT_SAME_SLOT_PENALTY

    return penalty


def _batch_one_recent_repeat_penalty(
    *,
    recipe_id: int,
    slot_index: int,
    day_date: date,
    slot_recipe_dates: dict[int, dict[int, list[date]]],
    current_day_selected_recipe_ids_by_slot_index: dict[int, int] | None,
) -> Decimal:
    penalty = Decimal("0")
    same_slot_dates = slot_recipe_dates.get(slot_index, {}).get(recipe_id, [])
    recent_same_slot_dates_count = 0
    for existing_day in same_slot_dates:
        if existing_day >= day_date:
            continue
        distance = (day_date - existing_day).days
        if distance <= 6:
            recent_same_slot_dates_count += 1
        if distance in BATCH_ONE_RECENT_REPEAT_PENALTY_BY_DISTANCE:
            penalty += BATCH_ONE_RECENT_REPEAT_PENALTY_BY_DISTANCE[distance]

    projected_usage_count = recent_same_slot_dates_count + 1
    if projected_usage_count > BATCH_ONE_MAX_REPEAT_PER_SLOT_IN_7_DAYS:
        overuse_count = projected_usage_count - BATCH_ONE_MAX_REPEAT_PER_SLOT_IN_7_DAYS
        penalty += BATCH_ONE_REPEAT_OVERUSE_PENALTY * Decimal(overuse_count)

    if current_day_selected_recipe_ids_by_slot_index:
        for existing_slot_index, selected_recipe_id in current_day_selected_recipe_ids_by_slot_index.items():
            if existing_slot_index == slot_index:
                continue
            if selected_recipe_id == recipe_id:
                penalty += BATCH_ONE_SAME_DAY_CROSS_SLOT_REPEAT_PENALTY
                break
    return penalty


def _batch_one_projected_slot_usage_count(
    *,
    recipe_id: int,
    slot_index: int,
    day_date: date,
    slot_recipe_dates: dict[int, dict[int, list[date]]],
) -> int:
    same_slot_dates = slot_recipe_dates.get(slot_index, {}).get(recipe_id, [])
    recent_count = 0
    for existing_day in same_slot_dates:
        if existing_day >= day_date:
            continue
        if (day_date - existing_day).days <= 6:
            recent_count += 1
    return recent_count + 1


def _batch_one_has_adjacent_same_slot_repeat(
    *,
    recipe_id: int,
    slot_index: int,
    day_date: date,
    slot_recipe_dates: dict[int, dict[int, list[date]]],
) -> bool:
    same_slot_dates = slot_recipe_dates.get(slot_index, {}).get(recipe_id, [])
    return any(existing_day < day_date and (day_date - existing_day).days == 1 for existing_day in same_slot_dates)


def _recipe_main_ingredient_groups(recipe: Recipe) -> set[str]:
    groups: set[str] = set()
    for ingredient in recipe.ingredients:
        if ingredient.food is None:
            continue
        food_name = ingredient.food.name.casefold()
        if any(token in food_name for token in ("лосос", "тунец", "треск", "рыб")):
            groups.add("fish")
        if "тофу" in food_name:
            groups.add("tofu")
        if any(token in food_name for token in ("нут", "фасол", "чечевиц")):
            groups.add("legume")
    return groups


def _preference_bonus_for_recipe(
    *,
    recipe: Recipe,
    preferred_food_ids: set[int],
    preferred_categories: set[str],
) -> Decimal:
    if not preferred_food_ids and not preferred_categories:
        return Decimal("0")

    bonus = Decimal("0")
    seen_food_ids: set[int] = set()
    seen_categories: set[str] = set()

    for ingredient in recipe.ingredients:
        if ingredient.food_id in preferred_food_ids and ingredient.food_id not in seen_food_ids:
            seen_food_ids.add(ingredient.food_id)
            bonus += PREFERRED_FOOD_BONUS

        category = ingredient.food.category.strip() if ingredient.food is not None else ""
        if category and category in preferred_categories and category not in seen_categories:
            seen_categories.add(category)
            bonus += PREFERRED_CATEGORY_BONUS

    return min(bonus, PREFERRED_BONUS_CAP)


def _score_recipe_candidate(
    recipe: Recipe,
    *,
    day_date: date,
    meals_per_day: int,
    slot_index: int,
    expected_meal_type: str,
    day_totals_before_slot: dict[str, Decimal],
    slot_weight: Decimal,
    servings_multiplier: Decimal,
    cumulative_weight: Decimal,
    targets: PlanTargets,
    recipe_usage_counts: dict[int, int],
    slot_recipe_dates: dict[int, dict[int, list[date]]],
    recipe_nutrients: dict[str, Decimal],
    preferred_food_ids: set[int] | None = None,
    preferred_categories: set[str] | None = None,
    favorite_recipe_ids: set[int] | None = None,
    favorite_recipes_mode: str = "none",
    max_cook_time_minutes: int | None = None,
    similarity_reference_names: list[str] | None = None,
    current_day_selected_recipe_ids_by_slot_index: dict[int, int] | None = None,
    historical_day_patterns: set[tuple[int, ...]] | None = None,
    meal_type_group_usage_counts: dict[str, int] | None = None,
    batch_days: int = 1,
) -> RecipeScore:
    nutrients = recipe_nutrients

    projected_day_kcal = day_totals_before_slot["kcal"] + nutrients["kcal"] * servings_multiplier
    projected_day_protein = day_totals_before_slot["protein"] + nutrients["protein"] * servings_multiplier
    projected_day_fat = day_totals_before_slot["fat"] + nutrients["fat"] * servings_multiplier
    projected_day_carbs = day_totals_before_slot["carbs"] + nutrients["carbs"] * servings_multiplier
    projected_day_fiber = day_totals_before_slot["fiber"] + nutrients["fiber"] * servings_multiplier

    expected_kcal = targets.kcal * cumulative_weight if targets.kcal is not None else None
    expected_protein = targets.protein * cumulative_weight if targets.protein is not None else None
    expected_fat = targets.fat * cumulative_weight if targets.fat is not None else None
    expected_carbs = targets.carbs * cumulative_weight if targets.carbs is not None else None
    expected_fiber = targets.fiber * cumulative_weight if targets.fiber is not None else None

    calorie_penalty = _relative_penalty(projected_day_kcal, expected_kcal, weight=CALORIE_PENALTY_WEIGHT)
    cumulative_macro_penalty = (
        _relative_penalty(projected_day_protein, expected_protein, weight=MACRO_PENALTY_WEIGHT)
        + _relative_penalty(projected_day_fat, expected_fat, weight=MACRO_PENALTY_WEIGHT)
        + _relative_penalty(projected_day_carbs, expected_carbs, weight=MACRO_PENALTY_WEIGHT)
    )

    protein_overshoot_penalty = _piecewise_penalty(
        _overshoot_ratio(projected_day_protein, targets.protein),
        weight=PROTEIN_OVERSHOOT_WEIGHT,
    )
    fat_overshoot_penalty = _piecewise_penalty(
        _overshoot_ratio(projected_day_fat, targets.fat),
        weight=FAT_OVERSHOOT_WEIGHT,
    )
    fat_overshoot_ratio = _overshoot_ratio(projected_day_fat, targets.fat)
    if fat_overshoot_ratio > HIGH_FAT_OVERSHOOT_RATIO:
        fat_overshoot_penalty += _piecewise_penalty(
            fat_overshoot_ratio - HIGH_FAT_OVERSHOOT_RATIO,
            weight=HIGH_FAT_OVERSHOOT_EXTRA_WEIGHT,
            mild_ratio=Decimal("0.08"),
            sharp_ratio=Decimal("0.18"),
        )
    fat_undershoot_penalty = _piecewise_penalty(
        _undershoot_ratio(projected_day_fat, targets.fat),
        weight=FAT_UNDERSHOOT_WEIGHT,
    )
    carbs_undershoot_ratio = _undershoot_ratio(projected_day_carbs, targets.carbs)
    carbs_undershoot_penalty = _piecewise_penalty(
        carbs_undershoot_ratio,
        weight=CARBS_UNDERSHOOT_WEIGHT,
    )
    if (
        expected_kcal is not None
        and expected_kcal > 0
        and abs(projected_day_kcal - expected_kcal) / expected_kcal <= KCAL_CLOSE_TO_EXPECTED_RATIO
        and carbs_undershoot_ratio > CARBS_NEAR_TARGET_UNDERSHOOT_RATIO
    ):
        carbs_undershoot_penalty += _piecewise_penalty(
            carbs_undershoot_ratio - CARBS_NEAR_TARGET_UNDERSHOOT_RATIO,
            weight=CARBS_NEAR_TARGET_EXTRA_WEIGHT,
            mild_ratio=Decimal("0.06"),
            sharp_ratio=Decimal("0.18"),
        )

    fiber_undershoot_penalty = _piecewise_penalty(
        _undershoot_ratio(projected_day_fiber, expected_fiber),
        weight=FIBER_UNDERSHOOT_WEIGHT,
        mild_ratio=Decimal("0.12"),
        sharp_ratio=Decimal("0.30"),
    )
    fiber_overshoot_penalty = Decimal("0")
    if targets.fiber is not None and targets.fiber > 0:
        overshoot_denominator = targets.fiber + FIBER_OVERSHOOT_MARGIN_GRAMS
        if overshoot_denominator > 0:
            fiber_overshoot_ratio = _overshoot_ratio(
                projected_day_fiber,
                targets.fiber + FIBER_OVERSHOOT_MARGIN_GRAMS,
            )
            fiber_overshoot_penalty = _piecewise_penalty(
                fiber_overshoot_ratio,
                weight=FIBER_OVERSHOOT_WEIGHT,
                mild_ratio=Decimal("0.10"),
                sharp_ratio=Decimal("0.28"),
            )

    remaining_balance_penalty = Decimal("0")
    remaining_weight = max(Decimal("0"), Decimal("1") - cumulative_weight)
    if targets.carbs is not None and targets.carbs > 0 and remaining_weight > 0:
        remaining_carbs_needed = max(Decimal("0"), targets.carbs - projected_day_carbs)
        expected_remaining_carbs = targets.carbs * remaining_weight
        if remaining_carbs_needed > expected_remaining_carbs:
            remaining_balance_penalty += _piecewise_penalty(
                (remaining_carbs_needed - expected_remaining_carbs) / expected_remaining_carbs,
                weight=REMAINING_BALANCE_WEIGHT,
            )
    if targets.fat is not None and targets.fat > 0 and remaining_weight > 0:
        remaining_fat_needed = max(Decimal("0"), targets.fat - projected_day_fat)
        expected_remaining_fat = targets.fat * remaining_weight
        if remaining_fat_needed > expected_remaining_fat:
            remaining_balance_penalty += _piecewise_penalty(
                (remaining_fat_needed - expected_remaining_fat) / expected_remaining_fat,
                weight=REMAINING_BALANCE_WEIGHT * Decimal("0.9"),
                mild_ratio=Decimal("0.08"),
                sharp_ratio=Decimal("0.22"),
            )
        expected_fat_so_far = targets.fat * cumulative_weight
        if expected_fat_so_far > 0 and projected_day_fat > expected_fat_so_far:
            remaining_balance_penalty += _piecewise_penalty(
                (projected_day_fat - expected_fat_so_far) / expected_fat_so_far,
                weight=REMAINING_BALANCE_WEIGHT * Decimal("1.2"),
                mild_ratio=Decimal("0.05"),
                sharp_ratio=Decimal("0.15"),
            )
    if targets.protein is not None and targets.protein > 0 and remaining_weight > 0:
        remaining_protein_budget = max(Decimal("0"), targets.protein - projected_day_protein)
        expected_remaining_protein = targets.protein * remaining_weight
        tight_budget = expected_remaining_protein * Decimal("0.50")
        if tight_budget > 0 and remaining_protein_budget < tight_budget:
            remaining_balance_penalty += _piecewise_penalty(
                (tight_budget - remaining_protein_budget) / tight_budget,
                weight=REMAINING_BALANCE_WEIGHT,
                mild_ratio=Decimal("0.08"),
                sharp_ratio=Decimal("0.20"),
            )

    macro_profile_penalty = Decimal("0")
    carbs_so_far_deficit_ratio = _undershoot_ratio(projected_day_carbs, expected_carbs)
    fat_so_far_deficit_ratio = _undershoot_ratio(projected_day_fat, expected_fat)
    protein_overshoot_ratio = _overshoot_ratio(projected_day_protein, targets.protein)
    if carbs_so_far_deficit_ratio > Decimal("0.10"):
        if is_protein_heavy(nutrients) and not is_carb_heavy(nutrients):
            macro_profile_penalty += carbs_so_far_deficit_ratio * MACRO_PROFILE_PENALTY_WEIGHT * Decimal("1.8")
        elif is_balanced_macro_profile(nutrients):
            macro_profile_penalty += carbs_so_far_deficit_ratio * MACRO_PROFILE_PENALTY_WEIGHT * Decimal("0.5")
        else:
            macro_profile_penalty += carbs_so_far_deficit_ratio * MACRO_PROFILE_PENALTY_WEIGHT
    if protein_overshoot_ratio > Decimal("0.05") and is_protein_heavy(nutrients):
        macro_profile_penalty += protein_overshoot_ratio * MACRO_PROFILE_PENALTY_WEIGHT * Decimal("1.6")
    if is_fat_heavy(nutrients) and fat_overshoot_ratio > Decimal("0.05"):
        macro_profile_penalty += fat_overshoot_ratio * MACRO_PROFILE_PENALTY_WEIGHT * Decimal("1.25")
    if fat_so_far_deficit_ratio > Decimal("0.10"):
        if is_dry_low_fat_candidate(nutrients):
            macro_profile_penalty += fat_so_far_deficit_ratio * FAT_PROFILE_PENALTY_WEIGHT * Decimal("1.7")
        elif is_fat_friendly(nutrients):
            macro_profile_penalty += fat_so_far_deficit_ratio * FAT_PROFILE_PENALTY_WEIGHT * Decimal("0.35")
        elif is_balanced_macro_profile(nutrients):
            macro_profile_penalty += fat_so_far_deficit_ratio * FAT_PROFILE_PENALTY_WEIGHT * Decimal("0.55")
        else:
            macro_profile_penalty += fat_so_far_deficit_ratio * FAT_PROFILE_PENALTY_WEIGHT

    guardrail_penalty = Decimal("0")
    if (
        targets.protein is not None
        and targets.protein > 0
        and projected_day_protein > (targets.protein * PROTEIN_OVERSHOOT_HARD_LIMIT)
    ):
        guardrail_penalty += HUGE_GUARDRAIL_PENALTY

    if (
        targets.carbs is not None
        and expected_carbs is not None
        and expected_carbs > 0
        and slot_weight >= LARGE_SLOT_WEIGHT_THRESHOLD
        and projected_day_carbs < (expected_carbs * CARBS_SO_FAR_GUARDRAIL_RATIO)
    ):
        guardrail_penalty += HUGE_GUARDRAIL_PENALTY

    if (
        servings_multiplier > PROTEIN_DENSE_MULTIPLIER_THRESHOLD
        and is_protein_heavy(nutrients)
        and nutrients["carbs"] <= LOW_CARB_PER_SERVING_THRESHOLD
    ):
        guardrail_penalty += HUGE_GUARDRAIL_PENALTY

    guardrail_penalty += slot_guardrail_penalty(
        nutrients=nutrients,
        servings_multiplier=servings_multiplier,
        slot_weight=slot_weight,
        meals_per_day=meals_per_day,
        expected_meal_type=expected_meal_type,
        targets=targets,
    )

    if expected_kcal is not None and expected_kcal > 0:
        kcal_so_far_deviation = abs(projected_day_kcal - expected_kcal) / expected_kcal
        if projected_day_kcal > expected_kcal * Decimal("1.15"):
            guardrail_penalty += _piecewise_penalty(
                (projected_day_kcal - (expected_kcal * Decimal("1.15"))) / (expected_kcal * Decimal("1.15")),
                weight=DAY_KCAL_OVERSHOOT_GUARDRAIL_WEIGHT,
                mild_ratio=Decimal("0.06"),
                sharp_ratio=Decimal("0.18"),
            )
        if (
            targets.kcal is not None
            and targets.kcal > 0
            and cumulative_weight >= Decimal("0.95")
            and projected_day_kcal > targets.kcal * Decimal("1.15")
        ):
            guardrail_penalty += _piecewise_penalty(
                (projected_day_kcal - (targets.kcal * Decimal("1.15"))) / (targets.kcal * Decimal("1.15")),
                weight=DAY_KCAL_OVERSHOOT_GUARDRAIL_WEIGHT * Decimal("1.25"),
                mild_ratio=Decimal("0.04"),
                sharp_ratio=Decimal("0.12"),
            )
        carbs_so_far_ratio = Decimal("1")
        if expected_carbs is not None and expected_carbs > 0:
            carbs_so_far_ratio = projected_day_carbs / expected_carbs
        if kcal_so_far_deviation <= Decimal("0.15") and (
            protein_overshoot_ratio >= Decimal("0.20") or carbs_so_far_ratio <= Decimal("0.70")
        ):
            guardrail_penalty += HUGE_GUARDRAIL_PENALTY / Decimal("2")

    if targets.kcal is not None and targets.kcal > 0 and targets.kcal <= MEDIUM_PROFILE_KCAL_THRESHOLD:
        kcal_overshoot_ratio = _overshoot_ratio(projected_day_kcal, targets.kcal)
        protein_overshoot_ratio = _overshoot_ratio(projected_day_protein, targets.protein)
        fat_overshoot_ratio = _overshoot_ratio(projected_day_fat, targets.fat)
        if kcal_overshoot_ratio > MEDIUM_PROFILE_OVER_KCAL_TRIGGER:
            macro_profile_penalty += protein_overshoot_ratio * MEDIUM_PROFILE_PROTEIN_FAT_EXTRA_WEIGHT
            macro_profile_penalty += fat_overshoot_ratio * MEDIUM_PROFILE_PROTEIN_FAT_EXTRA_WEIGHT
        if (
            cumulative_weight >= Decimal("0.95")
            and projected_day_kcal > targets.kcal * DAY_EXTREME_KCAL_RATIO
            and targets.protein is not None
            and projected_day_protein > targets.protein * DAY_EXTREME_PROTEIN_RATIO
            and targets.fat is not None
            and projected_day_fat > targets.fat * DAY_EXTREME_FAT_RATIO
        ):
            guardrail_penalty += HUGE_GUARDRAIL_PENALTY

    if targets.carbs is not None and targets.carbs >= HIGH_CARB_TARGET_THRESHOLD:
        carbs_deficit_ratio = _undershoot_ratio(projected_day_carbs, targets.carbs)
        if carbs_deficit_ratio > Decimal("0.08"):
            carbs_undershoot_penalty += _piecewise_penalty(
                carbs_deficit_ratio,
                weight=HIGH_CARB_PROFILE_CARBS_EXTRA_WEIGHT,
                mild_ratio=Decimal("0.06"),
                sharp_ratio=Decimal("0.18"),
            )

        protein_is_high = (
            targets.protein is not None
            and targets.protein > 0
            and projected_day_protein > targets.protein * HIGH_CARB_PROFILE_PROTEIN_OVERSHOOT_RATIO
        )
        carbs_is_low = projected_day_carbs < targets.carbs * HIGH_CARB_PROFILE_LOW_CARB_GUARDRAIL_RATIO

        if carbs_deficit_ratio > Decimal("0.12") and is_protein_heavy(nutrients):
            macro_profile_penalty += carbs_deficit_ratio * HIGH_CARB_PROFILE_PROTEIN_HEAVY_WEIGHT
        if protein_is_high and carbs_is_low and is_protein_heavy(nutrients) and not is_carb_heavy(nutrients):
            guardrail_penalty += HUGE_GUARDRAIL_PENALTY / Decimal("2")

        if (
            targets.fat is not None
            and targets.fat > 0
            and projected_day_fat <= targets.fat * Decimal("1.05")
            and carbs_deficit_ratio > Decimal("0.14")
            and is_protein_heavy(nutrients)
            and not is_carb_heavy(nutrients)
        ):
            macro_profile_penalty += carbs_deficit_ratio * HIGH_CARB_PROFILE_PROTEIN_HEAVY_WEIGHT * Decimal("1.15")

    guardrail_penalty += _day_pattern_repeat_penalty(
        slot_index=slot_index,
        candidate_recipe_id=recipe.id,
        meals_per_day=meals_per_day,
        current_day_selected_recipe_ids_by_slot_index=current_day_selected_recipe_ids_by_slot_index,
        historical_day_patterns=historical_day_patterns,
    )
    name_similarity_penalty = _recipe_name_similarity_penalty(
        recipe_name=recipe.name,
        reference_recipe_names=similarity_reference_names,
    )
    preference_bonus = _preference_bonus_for_recipe(
        recipe=recipe,
        preferred_food_ids=preferred_food_ids or set(),
        preferred_categories=preferred_categories or set(),
    )
    favorite_bonus = Decimal("0")
    if favorite_recipes_mode == "prefer" and favorite_recipe_ids and recipe.id in favorite_recipe_ids:
        favorite_bonus = FAVORITE_RECIPE_BONUS
    cook_time_penalty = Decimal("0")
    if max_cook_time_minutes is not None and recipe.cook_time_minutes is None:
        cook_time_penalty = UNKNOWN_COOK_TIME_PENALTY_WHEN_LIMITED
    batch_one_diversity_penalty = Decimal("0")
    if batch_days <= 1:
        batch_one_diversity_penalty = _batch_one_recent_repeat_penalty(
            recipe_id=recipe.id,
            slot_index=slot_index,
            day_date=day_date,
            slot_recipe_dates=slot_recipe_dates,
            current_day_selected_recipe_ids_by_slot_index=current_day_selected_recipe_ids_by_slot_index,
        )
    ingredient_group_penalty = Decimal("0")
    if batch_days <= 1 and meal_type_group_usage_counts:
        recipe_groups = _recipe_main_ingredient_groups(recipe)
        for group in recipe_groups:
            existing_count = int(meal_type_group_usage_counts.get(group, 0))
            if existing_count >= 2:
                ingredient_group_penalty += MAIN_INGREDIENT_GROUP_PENALTY_BY_GROUP[group] * Decimal(existing_count - 1)

    macro_penalty = (
        cumulative_macro_penalty
        + protein_overshoot_penalty
        + fat_overshoot_penalty
        + fat_undershoot_penalty
        + carbs_undershoot_penalty
        + fiber_undershoot_penalty
        + fiber_overshoot_penalty
        + remaining_balance_penalty
        + macro_profile_penalty
        + guardrail_penalty
        + name_similarity_penalty
        + cook_time_penalty
        + batch_one_diversity_penalty
        + ingredient_group_penalty
    )

    slot_penalty = Decimal("0")
    if expected_meal_type not in _normalize_recipe_meal_types(recipe):
        slot_penalty = SLOT_MISMATCH_PENALTY

    raw_repeat_penalty = _calculate_repeat_penalty(
        recipe_id=recipe.id,
        slot_index=slot_index,
        day_date=day_date,
        recipe_usage_counts=recipe_usage_counts,
        slot_recipe_dates=slot_recipe_dates,
    )
    repeat_penalty_cap = max(
        REPEAT_PENALTY_CAP_FLOOR,
        (calorie_penalty + macro_penalty) * REPEAT_PENALTY_CAP_BY_MACRO_FIT_FACTOR,
    )
    repeat_penalty = min(raw_repeat_penalty, repeat_penalty_cap)

    return RecipeScore(
        total_score=calorie_penalty + macro_penalty + slot_penalty + repeat_penalty - preference_bonus - favorite_bonus,
        repeat_penalty=repeat_penalty,
        calorie_penalty=calorie_penalty,
        macro_penalty=macro_penalty,
        slot_penalty=slot_penalty,
    )


def build_candidate_pool(
    *,
    candidates: list[Recipe],
    multiplier_candidates: tuple[Decimal, ...],
    meals_per_day: int,
    expected_meal_type: str,
    slot_weight: Decimal,
    targets: PlanTargets,
    recipe_nutrients_cache: dict[int, dict[str, Decimal]],
) -> list[CandidateOption]:
    """
    Candidate generation layer: build deterministic (recipe, multiplier) options.
    """
    options: list[CandidateOption] = []
    reasonable_options: list[CandidateOption] = []
    for recipe in candidates:
        recipe_nutrients = _recipe_nutrients_per_serving(recipe, recipe_nutrients_cache=recipe_nutrients_cache)
        max_multiplier = _max_multiplier_for_recipe(recipe_nutrients)
        for multiplier in multiplier_candidates:
            if multiplier > max_multiplier:
                continue
            option = CandidateOption(
                recipe=recipe,
                servings_multiplier=multiplier,
                nutrients=recipe_nutrients,
            )
            options.append(option)

            if is_candidate_reasonable_for_slot(
                nutrients=recipe_nutrients,
                servings_multiplier=multiplier,
                slot_weight=slot_weight,
                meals_per_day=meals_per_day,
                expected_meal_type=expected_meal_type,
                targets=targets,
            ):
                reasonable_options.append(option)

    chosen_pool = reasonable_options if reasonable_options else options
    return sorted(chosen_pool, key=lambda option: (option.recipe.id, option.servings_multiplier))


def score_candidate(
    candidate: CandidateOption,
    *,
    day_date: date,
    meals_per_day: int,
    slot_index: int,
    expected_meal_type: str,
    day_totals_before_slot: dict[str, Decimal],
    slot_weight: Decimal,
    cumulative_weight: Decimal,
    targets: PlanTargets,
    recipe_usage_counts: dict[int, int],
    slot_recipe_dates: dict[int, dict[int, list[date]]],
    preferred_food_ids: set[int] | None = None,
    preferred_categories: set[str] | None = None,
    favorite_recipe_ids: set[int] | None = None,
    favorite_recipes_mode: str = "none",
    max_cook_time_minutes: int | None = None,
    similarity_reference_names: list[str] | None = None,
    current_day_selected_recipe_ids_by_slot_index: dict[int, int] | None = None,
    historical_day_patterns: set[tuple[int, ...]] | None = None,
    meal_type_group_usage_counts: dict[str, int] | None = None,
    batch_days: int = 1,
) -> RecipeScore:
    """Score layer: deterministic multi-criteria score for a single candidate option."""
    return _score_recipe_candidate(
        candidate.recipe,
        day_date=day_date,
        meals_per_day=meals_per_day,
        slot_index=slot_index,
        expected_meal_type=expected_meal_type,
        day_totals_before_slot=day_totals_before_slot,
        slot_weight=slot_weight,
        servings_multiplier=candidate.servings_multiplier,
        cumulative_weight=cumulative_weight,
        targets=targets,
        recipe_usage_counts=recipe_usage_counts,
        slot_recipe_dates=slot_recipe_dates,
        recipe_nutrients=candidate.nutrients,
        preferred_food_ids=preferred_food_ids,
        preferred_categories=preferred_categories,
        favorite_recipe_ids=favorite_recipe_ids,
        favorite_recipes_mode=favorite_recipes_mode,
        max_cook_time_minutes=max_cook_time_minutes,
        similarity_reference_names=similarity_reference_names,
        current_day_selected_recipe_ids_by_slot_index=current_day_selected_recipe_ids_by_slot_index,
        historical_day_patterns=historical_day_patterns,
        meal_type_group_usage_counts=meal_type_group_usage_counts,
        batch_days=batch_days,
    )


def choose_best_candidate(
    *,
    candidate_pool: list[CandidateOption],
    day_date: date,
    meals_per_day: int,
    slot_index: int,
    expected_meal_type: str,
    day_totals_before_slot: dict[str, Decimal],
    slot_weight: Decimal,
    cumulative_weight: Decimal,
    targets: PlanTargets,
    recipe_usage_counts: dict[int, int],
    slot_recipe_dates: dict[int, dict[int, list[date]]],
    preferred_food_ids: set[int] | None = None,
    preferred_categories: set[str] | None = None,
    favorite_recipe_ids: set[int] | None = None,
    favorite_recipes_mode: str = "none",
    max_cook_time_minutes: int | None = None,
    similarity_reference_names: list[str] | None = None,
    current_day_selected_recipe_ids_by_slot_index: dict[int, int] | None = None,
    historical_day_patterns: set[tuple[int, ...]] | None = None,
    meal_type_group_usage_counts: dict[str, int] | None = None,
    batch_days: int = 1,
) -> CandidateOption:
    """
    Selection layer: choose the best candidate with a stable tie-break.
    """
    if not candidate_pool:
        _raise_not_enough_recipes_error(meal_type=expected_meal_type, day_date=day_date)

    scored_candidates: list[tuple[tuple[Decimal, Decimal, Decimal, int, Decimal], CandidateOption]] = []

    for candidate in candidate_pool:
        score = score_candidate(
            candidate,
            day_date=day_date,
            meals_per_day=meals_per_day,
            slot_index=slot_index,
            expected_meal_type=expected_meal_type,
            day_totals_before_slot=day_totals_before_slot,
            slot_weight=slot_weight,
            cumulative_weight=cumulative_weight,
            targets=targets,
            recipe_usage_counts=recipe_usage_counts,
            slot_recipe_dates=slot_recipe_dates,
            preferred_food_ids=preferred_food_ids,
            preferred_categories=preferred_categories,
            favorite_recipe_ids=favorite_recipe_ids,
            favorite_recipes_mode=favorite_recipes_mode,
            max_cook_time_minutes=max_cook_time_minutes,
            similarity_reference_names=similarity_reference_names,
            current_day_selected_recipe_ids_by_slot_index=current_day_selected_recipe_ids_by_slot_index,
            historical_day_patterns=historical_day_patterns,
            meal_type_group_usage_counts=meal_type_group_usage_counts,
            batch_days=batch_days,
        )
        candidate_key = (
            score.total_score,
            score.repeat_penalty,
            score.calorie_penalty,
            candidate.recipe.id,
            candidate.servings_multiplier,
        )
        scored_candidates.append((candidate_key, candidate))

    if batch_days <= 1:
        no_adjacent_and_not_over_cap: list[tuple[tuple[Decimal, Decimal, Decimal, int, Decimal], CandidateOption]] = []
        not_over_cap: list[tuple[tuple[Decimal, Decimal, Decimal, int, Decimal], CandidateOption]] = []
        no_adjacent: list[tuple[tuple[Decimal, Decimal, Decimal, int, Decimal], CandidateOption]] = []
        for candidate_key, candidate in scored_candidates:
            projected_count = _batch_one_projected_slot_usage_count(
                recipe_id=candidate.recipe.id,
                slot_index=slot_index,
                day_date=day_date,
                slot_recipe_dates=slot_recipe_dates,
            )
            exceeds_cap = projected_count > BATCH_ONE_MAX_REPEAT_PER_SLOT_IN_7_DAYS
            adjacent_repeat = _batch_one_has_adjacent_same_slot_repeat(
                recipe_id=candidate.recipe.id,
                slot_index=slot_index,
                day_date=day_date,
                slot_recipe_dates=slot_recipe_dates,
            )
            if not adjacent_repeat and not exceeds_cap:
                no_adjacent_and_not_over_cap.append((candidate_key, candidate))
            if not exceeds_cap:
                not_over_cap.append((candidate_key, candidate))
            if not adjacent_repeat:
                no_adjacent.append((candidate_key, candidate))

        if no_adjacent_and_not_over_cap:
            scored_candidates = no_adjacent_and_not_over_cap
        elif not_over_cap:
            scored_candidates = not_over_cap
        elif no_adjacent:
            scored_candidates = no_adjacent

    best_key, best_candidate = min(scored_candidates, key=lambda item: item[0], default=(None, None))

    if best_candidate is None:
        _raise_not_enough_recipes_error(meal_type=expected_meal_type, day_date=day_date)
    return best_candidate


def _select_slot_candidate(
    *,
    candidates: list[Recipe],
    multiplier_candidates: tuple[Decimal, ...],
    meals_per_day: int,
    expected_meal_type: str,
    day_date: date,
    slot_index: int,
    day_totals_before_slot: dict[str, Decimal],
    slot_weight: Decimal,
    cumulative_weight: Decimal,
    targets: PlanTargets,
    recipe_usage_counts: dict[int, int],
    slot_recipe_dates: dict[int, dict[int, list[date]]],
    recipe_nutrients_cache: dict[int, dict[str, Decimal]],
    preferred_food_ids: set[int] | None = None,
    preferred_categories: set[str] | None = None,
    favorite_recipe_ids: set[int] | None = None,
    favorite_recipes_mode: str = "none",
    max_cook_time_minutes: int | None = None,
    similarity_reference_names: list[str] | None = None,
    current_day_selected_recipe_ids_by_slot_index: dict[int, int] | None = None,
    historical_day_patterns: set[tuple[int, ...]] | None = None,
    meal_type_group_usage_counts: dict[str, int] | None = None,
    batch_days: int = 1,
) -> tuple[Recipe, Decimal]:
    candidate_pool = build_candidate_pool(
        candidates=candidates,
        multiplier_candidates=multiplier_candidates,
        meals_per_day=meals_per_day,
        expected_meal_type=expected_meal_type,
        slot_weight=slot_weight,
        targets=targets,
        recipe_nutrients_cache=recipe_nutrients_cache,
    )
    best_candidate = choose_best_candidate(
        candidate_pool=candidate_pool,
        day_date=day_date,
        meals_per_day=meals_per_day,
        slot_index=slot_index,
        expected_meal_type=expected_meal_type,
        day_totals_before_slot=day_totals_before_slot,
        slot_weight=slot_weight,
        cumulative_weight=cumulative_weight,
        targets=targets,
        recipe_usage_counts=recipe_usage_counts,
        slot_recipe_dates=slot_recipe_dates,
        preferred_food_ids=preferred_food_ids,
        preferred_categories=preferred_categories,
        favorite_recipe_ids=favorite_recipe_ids,
        favorite_recipes_mode=favorite_recipes_mode,
        max_cook_time_minutes=max_cook_time_minutes,
        similarity_reference_names=similarity_reference_names,
        current_day_selected_recipe_ids_by_slot_index=current_day_selected_recipe_ids_by_slot_index,
        historical_day_patterns=historical_day_patterns,
        meal_type_group_usage_counts=meal_type_group_usage_counts,
        batch_days=batch_days,
    )
    return best_candidate.recipe, best_candidate.servings_multiplier


def build_candidate_pool_by_meal_type(
    db: Session,
    *,
    user_id: int,
    slot_templates: tuple[SlotTemplate, ...],
    use_public_recipes: bool,
    excluded_recipe_ids: list[int],
    excluded_food_ids: list[int],
    excluded_categories: list[str],
    excluded_terms: list[str],
    favorite_recipe_ids: set[int],
    favorite_recipes_mode: str,
    max_cook_time_minutes: int | None = None,
) -> dict[str, list[Recipe]]:
    """
    Build candidate recipes per meal type once, then reuse for all slots.
    """
    candidates_by_meal_type: dict[str, list[Recipe]] = {}
    for meal_type in sorted({template.meal_type for template in slot_templates}):
        candidates_by_meal_type[meal_type] = get_accessible_recipe_candidates(
            db,
            user_id=user_id,
            meal_type=meal_type,
            use_public_recipes=use_public_recipes,
            excluded_recipe_ids=excluded_recipe_ids,
            excluded_food_ids=excluded_food_ids,
            excluded_categories=excluded_categories,
            excluded_terms=excluded_terms,
            max_cook_time_minutes=max_cook_time_minutes,
        )
        if favorite_recipes_mode == "only":
            candidates_by_meal_type[meal_type] = [
                candidate
                for candidate in candidates_by_meal_type[meal_type]
                if candidate.id in favorite_recipe_ids
            ]
    return candidates_by_meal_type


def _ensure_favorite_only_feasibility(
    *,
    days_count: int,
    slot_templates: tuple[SlotTemplate, ...],
    candidates_by_meal_type: dict[str, list[Recipe]],
    batch_cooking: dict[str, int],
    favorite_recipes_mode: str,
) -> None:
    if favorite_recipes_mode != "only":
        return

    for meal_type in {template.meal_type for template in slot_templates}:
        batch_days = int(batch_cooking.get(meal_type, 1))
        candidate_count = len(candidates_by_meal_type.get(meal_type, []))
        required_count = _recommended_candidates_for_batch(days_count=days_count, batch_days=batch_days)
        if candidate_count < required_count:
            raise PlanAutogenerateNotEnoughRecipesError(FAVORITES_ONLY_FRIENDLY_MESSAGE)


def build_autogenerated_plan(
    db: Session,
    *,
    user_id: int,
    payload: PlanAutogenerateRequest,
) -> Plan:
    selected_profile, targets = select_profile_targets(
        db,
        user_id=user_id,
        profile_id=payload.profile_id,
    )
    preferences = build_autoplan_preferences(
        db,
        user_id=user_id,
        profile=selected_profile,
        payload=payload,
    )

    slot_templates = get_slot_templates(payload.meals_per_day)
    candidates_by_meal_type = build_candidate_pool_by_meal_type(
        db,
        user_id=user_id,
        slot_templates=slot_templates,
        use_public_recipes=payload.use_public_recipes,
        excluded_recipe_ids=payload.excluded_recipe_ids,
        excluded_food_ids=sorted(preferences.excluded_food_ids),
        excluded_categories=sorted(preferences.excluded_categories),
        excluded_terms=sorted(preferences.excluded_terms),
        favorite_recipe_ids=preferences.favorite_recipe_ids,
        favorite_recipes_mode=preferences.favorite_recipes_mode,
        max_cook_time_minutes=preferences.max_cook_time_minutes,
    )
    _ensure_favorite_only_feasibility(
        days_count=payload.days_count,
        slot_templates=slot_templates,
        candidates_by_meal_type=candidates_by_meal_type,
        batch_cooking=preferences.batch_cooking,
        favorite_recipes_mode=preferences.favorite_recipes_mode,
    )

    recipe_nutrients_cache: dict[int, dict[str, Decimal]] = {}
    run_feasibility_check(
        days_count=payload.days_count,
        meals_per_day=payload.meals_per_day,
        slot_templates=slot_templates,
        targets=targets,
        candidates_by_meal_type=candidates_by_meal_type,
        recipe_nutrients_cache=recipe_nutrients_cache,
        batch_cooking=preferences.batch_cooking,
        max_cook_time_minutes=preferences.max_cook_time_minutes,
    )

    planned_slots: list[tuple[date, int, int, Decimal]] = []
    recipe_usage_counts: dict[int, int] = defaultdict(int)
    slot_recipe_dates: dict[int, dict[int, list[date]]] = defaultdict(lambda: defaultdict(list))
    historical_day_patterns: set[tuple[int, ...]] = set()
    batch_remaining_by_slot_index: dict[int, int] = defaultdict(int)
    batch_selected_recipe_id_by_slot_index: dict[int, int] = {}
    batch_selected_multiplier_by_slot_index: dict[int, Decimal] = {}
    meal_type_group_usage_counts_by_slot_index: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    try:
        for day_offset in range(payload.days_count):
            day_date = payload.start_date + timedelta(days=day_offset)
            day_totals = _zero_totals()
            selected_day_recipe_ids_by_slot_index: dict[int, int] = {}

            cumulative_weight = Decimal("0")
            for slot_index, template in enumerate(slot_templates):
                cumulative_weight += template.weight
                batch_days = preferences.batch_cooking.get(template.meal_type, 1)
                if batch_days >= 2 and batch_remaining_by_slot_index[slot_index] > 0:
                    selected_recipe_id = batch_selected_recipe_id_by_slot_index.get(slot_index)
                    if selected_recipe_id is None:
                        _raise_not_enough_recipes_error(meal_type=template.meal_type, day_date=day_date)
                    selected_recipe = next(
                        (candidate for candidate in candidates_by_meal_type[template.meal_type] if candidate.id == selected_recipe_id),
                        None,
                    )
                    if selected_recipe is None:
                        _raise_not_enough_recipes_error(meal_type=template.meal_type, day_date=day_date)
                    selected_multiplier = batch_selected_multiplier_by_slot_index.get(slot_index, Decimal("1"))
                    batch_remaining_by_slot_index[slot_index] -= 1
                else:
                    selected_recipe, selected_multiplier = _select_slot_candidate(
                        candidates=candidates_by_meal_type[template.meal_type],
                        multiplier_candidates=_candidate_multipliers(),
                        meals_per_day=payload.meals_per_day,
                        expected_meal_type=template.meal_type,
                        day_date=day_date,
                        slot_index=slot_index,
                        day_totals_before_slot=day_totals,
                        slot_weight=template.weight,
                        cumulative_weight=cumulative_weight,
                        targets=targets,
                        recipe_usage_counts=recipe_usage_counts,
                        slot_recipe_dates=slot_recipe_dates,
                        recipe_nutrients_cache=recipe_nutrients_cache,
                        preferred_food_ids=preferences.preferred_food_ids,
                        preferred_categories=preferences.preferred_categories,
                        favorite_recipe_ids=preferences.favorite_recipe_ids,
                        favorite_recipes_mode=preferences.favorite_recipes_mode,
                        max_cook_time_minutes=preferences.max_cook_time_minutes,
                        current_day_selected_recipe_ids_by_slot_index=selected_day_recipe_ids_by_slot_index,
                        historical_day_patterns=historical_day_patterns,
                        meal_type_group_usage_counts=meal_type_group_usage_counts_by_slot_index.get(slot_index, {}),
                        batch_days=batch_days,
                    )
                    if batch_days >= 2:
                        batch_selected_recipe_id_by_slot_index[slot_index] = selected_recipe.id
                        batch_selected_multiplier_by_slot_index[slot_index] = selected_multiplier
                        batch_remaining_by_slot_index[slot_index] = batch_days - 1

                selected_nutrients = _recipe_nutrients_per_serving(
                    selected_recipe,
                    recipe_nutrients_cache=recipe_nutrients_cache,
                )
                _add_totals(
                    day_totals,
                    nutrients=selected_nutrients,
                    servings_multiplier=selected_multiplier,
                )

                planned_slots.append((day_date, slot_index, selected_recipe.id, selected_multiplier))
                selected_day_recipe_ids_by_slot_index[slot_index] = selected_recipe.id
                recipe_usage_counts[selected_recipe.id] += 1
                slot_recipe_dates[slot_index][selected_recipe.id].append(day_date)
                for group in _recipe_main_ingredient_groups(selected_recipe):
                    meal_type_group_usage_counts_by_slot_index[slot_index][group] += 1

            day_pattern = tuple(
                selected_day_recipe_ids_by_slot_index[idx]
                for idx in range(len(slot_templates))
                if idx in selected_day_recipe_ids_by_slot_index
            )
            if len(day_pattern) == len(slot_templates):
                historical_day_patterns.add(day_pattern)
    except PlanAutogenerateNotEnoughRecipesError as exc:
        raise PlanAutogenerateNotEnoughRecipesError(
            _map_not_enough_recipes_message(
                detail=str(exc),
                has_generalized_exclusions=bool(preferences.excluded_categories or preferences.excluded_terms),
            )
        ) from exc

    plan = Plan(
        owner_user_id=user_id,
        profile_id=selected_profile.id,
        start_date=payload.start_date,
        days_count=payload.days_count,
        meals_per_day=payload.meals_per_day,
        title=_build_autogenerated_plan_title(start_date=payload.start_date, custom_title=payload.title),
        target_kcal=selected_profile.target_kcal,
        target_protein=selected_profile.target_protein,
        target_fat=selected_profile.target_fat,
        target_carbs=selected_profile.target_carbs,
        target_fiber=selected_profile.target_fiber,
    )
    db.add(plan)
    db.flush()

    slots = [
        PlanSlot(
            plan_id=plan.id,
            day_date=day_date,
            slot_index=slot_index,
            recipe_id=recipe_id,
            servings_multiplier=servings_multiplier,
            pinned=False,
        )
        for day_date, slot_index, recipe_id, servings_multiplier in planned_slots
    ]
    db.add_all(slots)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return _load_plan_with_slots_for_user(db, user_id=user_id, plan_id=plan.id)


def replace_plan_slot(
    db: Session,
    *,
    user_id: int,
    plan_id: int,
    slot_id: int,
    payload: ReplacePlanSlotRequest,
) -> Plan:
    plan = _load_plan_with_slots_for_user(db, user_id=user_id, plan_id=plan_id)
    preferences = build_plan_preferences_for_slot_operations(
        profile=plan.profile,
        payload_excluded_food_ids=payload.excluded_food_ids,
        payload_max_cook_time_minutes=payload.max_cook_time_minutes,
    )
    slot = next((value for value in plan.slots if value.id == slot_id), None)
    if slot is None:
        raise PlanAutogenerateSlotNotFoundError("Plan slot not found")

    targets = select_plan_snapshot_targets(plan)
    template = _resolve_slot_template(meals_per_day=plan.meals_per_day, slot_index=slot.slot_index)

    day_slots = sorted(
        [value for value in plan.slots if value.day_date == slot.day_date],
        key=lambda value: (value.slot_index, value.id),
    )
    avoid_recipe_ids = {
        day_slot.recipe_id
        for day_slot in day_slots
        if day_slot.id != slot.id and day_slot.recipe_id is not None
    }
    if slot.recipe_id is not None:
        avoid_recipe_ids.add(slot.recipe_id)

    accessible_recipes = _load_accessible_recipes(
        db,
        user_id=user_id,
        use_public_recipes=payload.use_public_recipes,
    )
    recipe_name_by_id = {recipe.id: recipe.name for recipe in accessible_recipes}
    candidates = filter_candidates(
        candidates=accessible_recipes,
        expected_meal_type=template.meal_type,
        excluded_recipe_ids=payload.excluded_recipe_ids,
        excluded_food_ids=sorted(preferences.excluded_food_ids),
        excluded_categories=sorted(preferences.excluded_categories),
        excluded_terms=sorted(preferences.excluded_terms),
        max_cook_time_minutes=preferences.max_cook_time_minutes,
        avoid_recipe_ids=avoid_recipe_ids,
    )
    if not candidates:
        if preferences.excluded_categories or preferences.excluded_terms:
            raise PlanAutogenerateNotEnoughRecipesError(EXCLUSIONS_TOO_STRICT_FRIENDLY_MESSAGE)
        raise PlanAutogenerateNotEnoughRecipesError(
            "Не удалось найти другую подходящую замену для этого слота."
        )

    similarity_reference_names = [
        recipe_name_by_id[recipe_id]
        for recipe_id in sorted(avoid_recipe_ids.union(set(payload.excluded_recipe_ids)))
        if recipe_id in recipe_name_by_id
    ]

    recipe_usage_counts = _build_recipe_usage_counts(slots=list(plan.slots), excluded_slot_ids={slot.id})
    slot_recipe_dates = _build_slot_recipe_dates(slots=list(plan.slots), excluded_slot_ids={slot.id})

    recipe_by_id = _build_recipe_lookup(slots=list(plan.slots), extra_recipes=candidates)
    recipe_nutrients_cache: dict[int, dict[str, Decimal]] = {}

    day_totals_before_slot = _calculate_day_totals_before_slot(
        day_slots=day_slots,
        target_slot_index=slot.slot_index,
        selected_slot_candidate_by_slot_id={},
        recipe_by_id=recipe_by_id,
        recipe_nutrients_cache=recipe_nutrients_cache,
    )

    try:
        selected_recipe, selected_multiplier = _select_slot_candidate(
            candidates=candidates,
            multiplier_candidates=_candidate_multipliers(extra_candidates=[slot.servings_multiplier]),
            meals_per_day=plan.meals_per_day,
            expected_meal_type=template.meal_type,
            day_date=slot.day_date,
            slot_index=slot.slot_index,
            day_totals_before_slot=day_totals_before_slot,
            slot_weight=template.weight,
            cumulative_weight=_cumulative_weight_for_slot(meals_per_day=plan.meals_per_day, slot_index=slot.slot_index),
            targets=targets,
            recipe_usage_counts=recipe_usage_counts,
            slot_recipe_dates=slot_recipe_dates,
            recipe_nutrients_cache=recipe_nutrients_cache,
            preferred_food_ids=preferences.preferred_food_ids,
            preferred_categories=preferences.preferred_categories,
            max_cook_time_minutes=preferences.max_cook_time_minutes,
            similarity_reference_names=similarity_reference_names,
        )
    except PlanAutogenerateNotEnoughRecipesError as exc:
        if preferences.excluded_categories or preferences.excluded_terms:
            raise PlanAutogenerateNotEnoughRecipesError(EXCLUSIONS_TOO_STRICT_FRIENDLY_MESSAGE) from exc
        raise PlanAutogenerateNotEnoughRecipesError(
            "Не удалось найти другую подходящую замену для этого слота."
        ) from exc

    clear_slot_ingredient_overrides(db, slot_id=slot.id)
    slot.recipe_id = selected_recipe.id
    slot.servings_multiplier = selected_multiplier
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return _load_plan_with_slots_for_user(db, user_id=user_id, plan_id=plan.id)


def _select_day_slot_candidates(
    db: Session,
    *,
    user_id: int,
    plan: Plan,
    day_date: date,
    day_slots: list[PlanSlot],
    mutable_slots: list[PlanSlot],
    targets: PlanTargets,
    payload: RegeneratePlanDayRequest,
    preferences: AutoplanPreferences,
    recipe_usage_counts: dict[int, int],
    slot_recipe_dates: dict[int, dict[int, list[date]]],
    avoid_current_recipes: bool,
    strict_require_candidates: bool,
) -> tuple[dict[int, tuple[int, Decimal]], dict[int, Recipe]] | None:
    selected_slot_candidate_by_slot_id: dict[int, tuple[int, Decimal]] = {}
    recipe_by_id = _build_recipe_lookup(slots=list(plan.slots))
    recipe_nutrients_cache: dict[int, dict[str, Decimal]] = {}
    local_recipe_usage_counts = dict(recipe_usage_counts)
    local_slot_recipe_dates = {
        slot_index: {recipe_id: list(dates) for recipe_id, dates in by_recipe.items()}
        for slot_index, by_recipe in slot_recipe_dates.items()
    }

    for slot in mutable_slots:
        template = _resolve_slot_template(meals_per_day=plan.meals_per_day, slot_index=slot.slot_index)
        candidates = get_accessible_recipe_candidates(
            db,
            user_id=user_id,
            meal_type=template.meal_type,
            use_public_recipes=payload.use_public_recipes,
            excluded_recipe_ids=payload.excluded_recipe_ids,
            excluded_food_ids=sorted(preferences.excluded_food_ids),
            excluded_categories=sorted(preferences.excluded_categories),
            excluded_terms=sorted(preferences.excluded_terms),
            max_cook_time_minutes=preferences.max_cook_time_minutes,
        )

        if avoid_current_recipes and slot.recipe_id is not None:
            variation_candidates = filter_candidates(
                candidates=candidates,
                expected_meal_type=template.meal_type,
                excluded_recipe_ids=payload.excluded_recipe_ids,
                excluded_food_ids=sorted(preferences.excluded_food_ids),
                excluded_categories=sorted(preferences.excluded_categories),
                excluded_terms=sorted(preferences.excluded_terms),
                max_cook_time_minutes=preferences.max_cook_time_minutes,
                avoid_recipe_ids={slot.recipe_id},
            )
            if variation_candidates:
                candidates = variation_candidates

        if not candidates:
            if strict_require_candidates:
                _raise_not_enough_recipes_error(meal_type=template.meal_type, day_date=day_date)
            return None

        for recipe in candidates:
            recipe_by_id[recipe.id] = recipe

        day_totals_before_slot = _calculate_day_totals_before_slot(
            day_slots=day_slots,
            target_slot_index=slot.slot_index,
            selected_slot_candidate_by_slot_id=selected_slot_candidate_by_slot_id,
            recipe_by_id=recipe_by_id,
            recipe_nutrients_cache=recipe_nutrients_cache,
        )

        try:
            selected_recipe, selected_multiplier = _select_slot_candidate(
                candidates=candidates,
                multiplier_candidates=_candidate_multipliers(extra_candidates=[slot.servings_multiplier]),
                meals_per_day=plan.meals_per_day,
                expected_meal_type=template.meal_type,
                day_date=day_date,
                slot_index=slot.slot_index,
                day_totals_before_slot=day_totals_before_slot,
                slot_weight=template.weight,
                cumulative_weight=_cumulative_weight_for_slot(meals_per_day=plan.meals_per_day, slot_index=slot.slot_index),
                targets=targets,
                recipe_usage_counts=local_recipe_usage_counts,
                slot_recipe_dates=local_slot_recipe_dates,
                recipe_nutrients_cache=recipe_nutrients_cache,
                preferred_food_ids=preferences.preferred_food_ids,
                preferred_categories=preferences.preferred_categories,
                favorite_recipe_ids=preferences.favorite_recipe_ids,
                favorite_recipes_mode=preferences.favorite_recipes_mode,
                max_cook_time_minutes=preferences.max_cook_time_minutes,
            )
        except PlanAutogenerateNotEnoughRecipesError:
            if strict_require_candidates:
                raise
            return None

        selected_slot_candidate_by_slot_id[slot.id] = (selected_recipe.id, selected_multiplier)
        local_recipe_usage_counts[selected_recipe.id] = local_recipe_usage_counts.get(selected_recipe.id, 0) + 1
        local_slot_recipe_dates.setdefault(slot.slot_index, {}).setdefault(selected_recipe.id, []).append(day_date)

    return selected_slot_candidate_by_slot_id, recipe_by_id


def regenerate_plan_day(
    db: Session,
    *,
    user_id: int,
    plan_id: int,
    day_date: date,
    payload: RegeneratePlanDayRequest,
) -> Plan:
    plan = _load_plan_with_slots_for_user(db, user_id=user_id, plan_id=plan_id)
    preferences = build_plan_preferences_for_slot_operations(
        profile=plan.profile,
        payload_excluded_food_ids=payload.excluded_food_ids,
        payload_max_cook_time_minutes=payload.max_cook_time_minutes,
    )
    end_date = plan.start_date + timedelta(days=plan.days_count - 1)
    if day_date < plan.start_date or day_date > end_date:
        raise PlanAutogenerateDayOutOfRangeError(
            f"Day {day_date.isoformat()} is out of plan range"
        )

    day_slots = sorted(
        [slot for slot in plan.slots if slot.day_date == day_date],
        key=lambda slot: (slot.slot_index, slot.id),
    )
    mutable_slots = [slot for slot in day_slots if not slot.pinned]
    if not mutable_slots:
        return plan

    targets = select_plan_snapshot_targets(plan)

    mutable_slot_ids = {slot.id for slot in mutable_slots}
    recipe_usage_counts = _build_recipe_usage_counts(
        slots=list(plan.slots),
        excluded_slot_ids=mutable_slot_ids,
    )
    slot_recipe_dates = _build_slot_recipe_dates(
        slots=list(plan.slots),
        excluded_slot_ids=mutable_slot_ids,
    )

    current_day_signature = {
        slot.id: (slot.recipe_id, slot.servings_multiplier)
        for slot in mutable_slots
    }

    selected_slot_candidate_by_slot_id: dict[int, tuple[int, Decimal]] | None = None
    variation_selection = _select_day_slot_candidates(
        db,
        user_id=user_id,
        plan=plan,
        day_date=day_date,
        day_slots=day_slots,
        mutable_slots=mutable_slots,
        targets=targets,
        payload=payload,
        preferences=preferences,
        recipe_usage_counts=recipe_usage_counts,
        slot_recipe_dates=slot_recipe_dates,
        avoid_current_recipes=True,
        strict_require_candidates=False,
    )
    if variation_selection is not None:
        variation_selected_map, variation_recipe_lookup = variation_selection
        changed_non_pinned_slot = any(
            variation_selected_map[slot.id] != current_day_signature.get(slot.id)
            for slot in mutable_slots
        )
        if changed_non_pinned_slot:
            baseline_cache: dict[int, dict[str, Decimal]] = {}
            candidate_cache: dict[int, dict[str, Decimal]] = {}
            baseline_totals = _calculate_day_totals(
                day_slots=day_slots,
                selected_slot_candidate_by_slot_id=None,
                recipe_by_id=variation_recipe_lookup,
                recipe_nutrients_cache=baseline_cache,
            )
            candidate_totals = _calculate_day_totals(
                day_slots=day_slots,
                selected_slot_candidate_by_slot_id=variation_selected_map,
                recipe_by_id=variation_recipe_lookup,
                recipe_nutrients_cache=candidate_cache,
            )
            if _is_day_variation_acceptable(
                baseline_totals=baseline_totals,
                candidate_totals=candidate_totals,
                targets=targets,
            ):
                selected_slot_candidate_by_slot_id = variation_selected_map

    if selected_slot_candidate_by_slot_id is None:
        try:
            fallback_selection = _select_day_slot_candidates(
                db,
                user_id=user_id,
                plan=plan,
                day_date=day_date,
                day_slots=day_slots,
                mutable_slots=mutable_slots,
                targets=targets,
                payload=payload,
                preferences=preferences,
                recipe_usage_counts=recipe_usage_counts,
                slot_recipe_dates=slot_recipe_dates,
                avoid_current_recipes=False,
                strict_require_candidates=True,
            )
        except PlanAutogenerateNotEnoughRecipesError as exc:
            if preferences.excluded_categories or preferences.excluded_terms:
                raise PlanAutogenerateNotEnoughRecipesError(EXCLUSIONS_TOO_STRICT_FRIENDLY_MESSAGE) from exc
            raise PlanAutogenerateNotEnoughRecipesError(
                "Не удалось подобрать блюда для выбранного дня с текущими ограничениями."
            ) from exc
        if fallback_selection is None:
            if preferences.excluded_categories or preferences.excluded_terms:
                raise PlanAutogenerateNotEnoughRecipesError(EXCLUSIONS_TOO_STRICT_FRIENDLY_MESSAGE)
            raise PlanAutogenerateNotEnoughRecipesError(
                "Не удалось подобрать блюда для выбранного дня с текущими ограничениями."
            )
        selected_slot_candidate_by_slot_id, _ = fallback_selection

    for slot in mutable_slots:
        previous_recipe_id = slot.recipe_id
        selected_recipe_id, selected_multiplier = selected_slot_candidate_by_slot_id[slot.id]
        if selected_recipe_id != previous_recipe_id:
            clear_slot_ingredient_overrides(db, slot_id=slot.id)
        slot.recipe_id = selected_recipe_id
        slot.servings_multiplier = selected_multiplier

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return _load_plan_with_slots_for_user(db, user_id=user_id, plan_id=plan.id)


def autogenerate_plan(
    db: Session,
    *,
    user_id: int,
    payload: PlanAutogenerateRequest,
) -> Plan:
    """Public entrypoint with explicit algorithm naming for docs and VKR chapter."""
    return build_autogenerated_plan(
        db,
        user_id=user_id,
        payload=payload,
    )


def replace_slot(
    db: Session,
    *,
    user_id: int,
    plan_id: int,
    slot_id: int,
    payload: ReplacePlanSlotRequest,
) -> Plan:
    return replace_plan_slot(
        db,
        user_id=user_id,
        plan_id=plan_id,
        slot_id=slot_id,
        payload=payload,
    )


def regenerate_day(
    db: Session,
    *,
    user_id: int,
    plan_id: int,
    day_date: date,
    payload: RegeneratePlanDayRequest,
) -> Plan:
    return regenerate_plan_day(
        db,
        user_id=user_id,
        plan_id=plan_id,
        day_date=day_date,
        payload=payload,
    )
