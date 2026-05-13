from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.services.recipes import seed_demo_public_recipes
from test_plans_api import (
    add_ingredient_via_api,
    auth_headers,
    create_food_via_api,
    create_recipe_via_api,
    create_user_with_token,
    publish_recipe_via_api,
    withdraw_recipe_via_api,
)

MEAL_SEQUENCE_BY_MEALS_PER_DAY = {
    2: ["lunch", "dinner"],
    3: ["breakfast", "lunch", "dinner"],
    4: ["breakfast", "lunch", "dinner", "snack"],
    5: ["breakfast", "snack", "lunch", "dinner", "snack"],
    6: ["breakfast", "snack", "lunch", "snack", "dinner", "snack"],
}

SLOT_WEIGHTS_BY_MEALS_PER_DAY = {
    2: [Decimal("0.45"), Decimal("0.55")],
    3: [Decimal("0.25"), Decimal("0.40"), Decimal("0.35")],
    4: [Decimal("0.25"), Decimal("0.35"), Decimal("0.30"), Decimal("0.10")],
    5: [Decimal("0.20"), Decimal("0.10"), Decimal("0.30"), Decimal("0.25"), Decimal("0.15")],
    6: [Decimal("0.20"), Decimal("0.10"), Decimal("0.25"), Decimal("0.10"), Decimal("0.25"), Decimal("0.10")],
}


def _create_recipe_with_ingredient(
    client: TestClient,
    token: str,
    *,
    name: str,
    meal_types: list[str],
    food_id: int,
    grams: str = "100",
) -> dict:
    recipe = create_recipe_via_api(
        client,
        token,
        name=name,
        servings_count=1,
        meal_types=meal_types,
    )
    add_ingredient_via_api(
        client,
        token,
        recipe_id=recipe["id"],
        food_id=food_id,
        grams=grams,
    )
    return recipe


def _create_recipe_with_ingredient_and_cook_time(
    client: TestClient,
    token: str,
    *,
    name: str,
    meal_types: list[str],
    food_id: int,
    cook_time_minutes: int,
    grams: str = "100",
) -> dict:
    recipe_response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json={
            "name": name,
            "servings_count": 1,
            "meal_types": meal_types,
            "cook_time_minutes": cook_time_minutes,
        },
    )
    assert recipe_response.status_code == 201, recipe_response.text
    recipe = recipe_response.json()
    add_ingredient_via_api(
        client,
        token,
        recipe_id=recipe["id"],
        food_id=food_id,
        grams=grams,
    )
    return recipe


def _post_autogenerate_plan(
    client: TestClient,
    token: str,
    payload: dict,
):
    return client.post(
        "/plans/autogenerate",
        headers=auth_headers(token),
        json=payload,
    )


def _create_profile_via_api(
    client: TestClient,
    token: str,
    *,
    name: str,
    target_kcal: int | None,
    target_protein: int | None = None,
    target_fat: int | None = None,
    target_carbs: int | None = None,
) -> dict:
    response = client.post(
        "/profiles",
        headers=auth_headers(token),
        json={
            "name": name,
            "target_kcal": target_kcal,
            "target_protein": target_protein,
            "target_fat": target_fat,
            "target_carbs": target_carbs,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _list_profiles(client: TestClient, token: str) -> list[dict]:
    response = client.get("/profiles", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


def _patch_profile_via_api(client: TestClient, token: str, profile_id: int, payload: dict) -> dict:
    response = client.patch(
        f"/profiles/{profile_id}",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_two_meal_pool(client: TestClient, token: str) -> tuple[dict, dict]:
    lunch_food = create_food_via_api(
        client,
        token,
        name="Autoplan Profile Lunch Food",
        kcal="450.00",
        protein="30.00",
        fat="15.00",
        carbs="50.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Autoplan Profile Dinner Food",
        kcal="600.00",
        protein="35.00",
        fat="20.00",
        carbs="55.00",
    )
    lunch_recipe = _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Profile Lunch",
        meal_types=["lunch"],
        food_id=lunch_food["id"],
    )
    dinner_recipe = _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Profile Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )
    return lunch_recipe, dinner_recipe


def test_autogenerate_uses_profile_id_from_request_and_saves_snapshot(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_profile_id@example.com",
        username="autoplan_profile_id",
    )
    _create_two_meal_pool(client, token)
    explicit_profile = _create_profile_via_api(
        client,
        token,
        name="Cutting",
        target_kcal=1650,
        target_protein=130,
        target_fat=55,
        target_carbs=140,
    )

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 2,
            "meals_per_day": 2,
            "profile_id": explicit_profile["id"],
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    assert plan["profile_id"] == explicit_profile["id"]
    assert plan["profile_name"] == "Cutting"
    assert plan["target_kcal"] == 1650
    assert plan["target_protein"] == 130
    assert plan["target_fat"] == 55
    assert plan["target_carbs"] == 140


def test_autogenerate_falls_back_to_first_profile_when_profile_id_missing(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_profile_fallback@example.com",
        username="autoplan_profile_fallback",
    )
    _create_two_meal_pool(client, token)
    _create_profile_via_api(
        client,
        token,
        name="Bulk",
        target_kcal=2800,
    )

    profiles = _list_profiles(client, token)
    expected_default_profile_id = profiles[0]["id"]

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["profile_id"] == expected_default_profile_id


def test_autogenerate_returns_404_for_foreign_profile_id(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="autoplan_foreign_profile_owner@example.com",
        username="autoplan_foreign_profile_owner",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="autoplan_foreign_profile_other@example.com",
        username="autoplan_foreign_profile_other",
    )
    _create_two_meal_pool(client, owner_token)
    foreign_profile = _create_profile_via_api(
        client,
        other_token,
        name="Other profile",
        target_kcal=2100,
    )

    response = _post_autogenerate_plan(
        client,
        owner_token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "profile_id": foreign_profile["id"],
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Profile not found"


def test_autogenerate_returns_422_when_profile_has_no_kcal_target(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_missing_kcal@example.com",
        username="autoplan_missing_kcal",
    )
    _create_two_meal_pool(client, token)
    no_kcal_profile = _create_profile_via_api(
        client,
        token,
        name="No Kcal Profile",
        target_kcal=None,
        target_protein=120,
        target_fat=60,
        target_carbs=180,
    )

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "profile_id": no_kcal_profile["id"],
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 422, response.text
    assert "target_kcal" in response.json()["detail"]


def test_autogenerate_returns_422_for_low_feasibility_high_target_with_3_meals(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_low_feasibility_high_target@example.com",
        username="autoplan_low_feasibility_high_target",
    )

    breakfast_food = create_food_via_api(
        client,
        token,
        name="Low Feasibility Breakfast Food",
        kcal="180.00",
        protein="9.00",
        fat="4.00",
        carbs="28.00",
    )
    lunch_food = create_food_via_api(
        client,
        token,
        name="Low Feasibility Lunch Food",
        kcal="220.00",
        protein="15.00",
        fat="7.00",
        carbs="30.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Low Feasibility Dinner Food",
        kcal="260.00",
        protein="20.00",
        fat="9.00",
        carbs="32.00",
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Low Feasibility Breakfast Recipe",
        meal_types=["breakfast"],
        food_id=breakfast_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Low Feasibility Lunch Recipe",
        meal_types=["lunch"],
        food_id=lunch_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Low Feasibility Dinner Recipe",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )

    profile = _create_profile_via_api(
        client,
        token,
        name="High target profile",
        target_kcal=3530,
        target_protein=180,
        target_fat=90,
        target_carbs=500,
    )
    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 3,
            "profile_id": profile["id"],
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "доступных блюд недостаточно" in detail
    assert "4-5" in detail


def test_autogenerate_high_target_with_5_meals_is_feasible_with_seeded_pool(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
    finally:
        db.close()

    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_high_target_seeded_pool@example.com",
        username="autoplan_high_target_seeded_pool",
    )
    profile = _create_profile_via_api(
        client,
        token,
        name="Seeded high target profile",
        target_kcal=3200,
        target_protein=170,
        target_fat=95,
        target_carbs=430,
    )
    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 5,
            "profile_id": profile["id"],
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    assert len(plan["slots"]) == 5
    assert Decimal(str(plan["days"][0]["totals"]["kcal"])) >= Decimal("2600")
    assert Decimal(str(plan["days"][0]["totals"]["fat"])) >= Decimal("70")


def test_autogenerate_medium_profile_with_seeded_pool_stays_acceptable(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
    finally:
        db.close()

    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_medium_seeded_profile@example.com",
        username="autoplan_medium_seeded_profile",
    )
    profile = _create_profile_via_api(
        client,
        token,
        name="Seeded medium profile",
        target_kcal=2000,
        target_protein=120,
        target_fat=70,
        target_carbs=230,
    )
    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 3,
            "meals_per_day": 3,
            "profile_id": profile["id"],
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    assert len(plan["days"]) == 3

    for day in plan["days"]:
        day_kcal = Decimal(str(day["totals"]["kcal"]))
        day_fat = Decimal(str(day["totals"]["fat"]))
        assert day_kcal >= Decimal("1400")
        assert day_kcal <= Decimal("2600")
        assert day_fat >= Decimal("40")


def test_autogenerate_prefers_fat_friendly_candidate_when_fats_lagging(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_fat_lag_prefers_fat_friendly@example.com",
        username="autoplan_fat_lag_prefers_fat_friendly",
    )

    breakfast_food = create_food_via_api(
        client,
        token,
        name="Fat Lag Breakfast Food",
        kcal="240.00",
        protein="12.00",
        fat="3.00",
        carbs="40.00",
    )
    lunch_dry_food = create_food_via_api(
        client,
        token,
        name="Fat Lag Dry Lunch Food",
        kcal="500.00",
        protein="40.00",
        fat="5.00",
        carbs="55.00",
    )
    lunch_fat_friendly_food = create_food_via_api(
        client,
        token,
        name="Fat Lag Fat Friendly Lunch Food",
        kcal="500.00",
        protein="30.00",
        fat="20.00",
        carbs="50.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Fat Lag Dinner Food",
        kcal="760.00",
        protein="35.00",
        fat="18.00",
        carbs="92.00",
    )

    _create_recipe_with_ingredient(
        client,
        token,
        name="Fat Lag Breakfast",
        meal_types=["breakfast"],
        food_id=breakfast_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Fat Lag Dry Lunch",
        meal_types=["lunch"],
        food_id=lunch_dry_food["id"],
    )
    fat_friendly_lunch = _create_recipe_with_ingredient(
        client,
        token,
        name="Fat Lag Fat Friendly Lunch",
        meal_types=["lunch"],
        food_id=lunch_fat_friendly_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Fat Lag Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )

    profile = _create_profile_via_api(
        client,
        token,
        name="Fat lag profile",
        target_kcal=2200,
        target_protein=130,
        target_fat=85,
        target_carbs=250,
    )
    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 3,
            "profile_id": profile["id"],
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    lunch_slot = next(slot for slot in plan["slots"] if slot["slot_index"] == 1)
    assert lunch_slot["recipe_id"] == fat_friendly_lunch["id"]


def test_autogenerate_late_plan_macro_fit_can_beat_repeat_penalty(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_late_plan_macro_fit_over_repeat@example.com",
        username="autoplan_late_plan_macro_fit_over_repeat",
    )

    lunch_dry_food = create_food_via_api(
        client,
        token,
        name="Late Plan Dry Lunch Food",
        kcal="620.00",
        protein="55.00",
        fat="4.00",
        carbs="25.00",
    )
    lunch_balanced_food = create_food_via_api(
        client,
        token,
        name="Late Plan Balanced Lunch Food",
        kcal="620.00",
        protein="30.00",
        fat="22.00",
        carbs="70.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Late Plan Dinner Food",
        kcal="900.00",
        protein="35.00",
        fat="30.00",
        carbs="95.00",
    )

    _create_recipe_with_ingredient(
        client,
        token,
        name="Late Plan Dry Lunch",
        meal_types=["lunch"],
        food_id=lunch_dry_food["id"],
    )
    balanced_lunch = _create_recipe_with_ingredient(
        client,
        token,
        name="Late Plan Balanced Lunch",
        meal_types=["lunch"],
        food_id=lunch_balanced_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Late Plan Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )

    profile = _create_profile_via_api(
        client,
        token,
        name="Late plan profile",
        target_kcal=2200,
        target_protein=140,
        target_fat=85,
        target_carbs=280,
    )
    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 5,
            "meals_per_day": 2,
            "profile_id": profile["id"],
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    sorted_slots = sorted(plan["slots"], key=lambda slot: (slot["day_date"], slot["slot_index"]))
    last_day_lunch = next(slot for slot in reversed(sorted_slots) if slot["slot_index"] == 0)
    assert last_day_lunch["recipe_id"] == balanced_lunch["id"]


def test_autogenerate_high_kcal_profile_can_pick_multiplier_above_one(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_high_kcal_multiplier@example.com",
        username="autoplan_high_kcal_multiplier",
    )

    low_lunch_food = create_food_via_api(
        client,
        token,
        name="High Kcal Low Lunch",
        kcal="300.00",
        protein="20.00",
        fat="10.00",
        carbs="35.00",
    )
    low_dinner_food = create_food_via_api(
        client,
        token,
        name="High Kcal Low Dinner",
        kcal="400.00",
        protein="25.00",
        fat="14.00",
        carbs="42.00",
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="High Kcal Lunch Recipe",
        meal_types=["lunch"],
        food_id=low_lunch_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="High Kcal Dinner Recipe",
        meal_types=["dinner"],
        food_id=low_dinner_food["id"],
    )

    high_kcal_profile = _create_profile_via_api(
        client,
        token,
        name="High kcal profile",
        target_kcal=2200,
    )
    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "profile_id": high_kcal_profile["id"],
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    assert any(Decimal(str(slot["servings_multiplier"])) > Decimal("1.0") for slot in plan["slots"])


def test_autogenerate_prefers_carb_friendly_recipe_for_high_carb_profile(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_macro_balance_prefers_carbs@example.com",
        username="autoplan_macro_balance_prefers_carbs",
    )

    protein_heavy_food = create_food_via_api(
        client,
        token,
        name="Macro Balance Protein Heavy Lunch Food",
        kcal="460.00",
        protein="60.00",
        fat="12.00",
        carbs="8.00",
    )
    carb_friendly_food = create_food_via_api(
        client,
        token,
        name="Macro Balance Carb Friendly Lunch Food",
        kcal="420.00",
        protein="18.00",
        fat="10.00",
        carbs="68.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Macro Balance Dinner Food",
        kcal="800.00",
        protein="30.00",
        fat="25.00",
        carbs="96.00",
    )

    protein_heavy_lunch = _create_recipe_with_ingredient(
        client,
        token,
        name="Macro Balance Protein Heavy Lunch",
        meal_types=["lunch"],
        food_id=protein_heavy_food["id"],
    )
    carb_friendly_lunch = _create_recipe_with_ingredient(
        client,
        token,
        name="Macro Balance Carb Friendly Lunch",
        meal_types=["lunch"],
        food_id=carb_friendly_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Macro Balance Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )

    high_carb_profile = _create_profile_via_api(
        client,
        token,
        name="Macro Balance High Carb",
        target_kcal=2200,
        target_protein=120,
        target_fat=70,
        target_carbs=280,
    )
    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "profile_id": high_carb_profile["id"],
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    lunch_slot = next(slot for slot in plan["slots"] if slot["slot_index"] == 0)
    assert lunch_slot["recipe_id"] == carb_friendly_lunch["id"]
    assert lunch_slot["recipe_id"] != protein_heavy_lunch["id"]


def test_autogenerate_caps_multiplier_without_2_5_option(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_multiplier_cap_no_2_5@example.com",
        username="autoplan_multiplier_cap_no_2_5",
    )

    lunch_food = create_food_via_api(
        client,
        token,
        name="Multiplier Cap Lunch Food",
        kcal="280.00",
        protein="18.00",
        fat="8.00",
        carbs="32.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Multiplier Cap Dinner Food",
        kcal="320.00",
        protein="20.00",
        fat="10.00",
        carbs="36.00",
    )

    _create_recipe_with_ingredient(
        client,
        token,
        name="Multiplier Cap Lunch",
        meal_types=["lunch"],
        food_id=lunch_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Multiplier Cap Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )

    profile = _create_profile_via_api(
        client,
        token,
        name="Multiplier Cap High kcal",
        target_kcal=2500,
    )
    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "profile_id": profile["id"],
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    multipliers = [Decimal(str(slot["servings_multiplier"])) for slot in plan["slots"]]
    assert all(multiplier <= Decimal("2.0") for multiplier in multipliers)
    assert any(multiplier > Decimal("1.0") for multiplier in multipliers)


def test_autogenerate_caps_multiplier_for_protein_dense_recipe(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_multiplier_cap_protein_dense@example.com",
        username="autoplan_multiplier_cap_protein_dense",
    )

    protein_dense_lunch_food = create_food_via_api(
        client,
        token,
        name="Protein Dense Only Lunch Food",
        kcal="420.00",
        protein="48.00",
        fat="10.00",
        carbs="18.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Protein Dense Only Dinner Food",
        kcal="450.00",
        protein="22.00",
        fat="14.00",
        carbs="52.00",
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Protein Dense Only Lunch",
        meal_types=["lunch"],
        food_id=protein_dense_lunch_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Protein Dense Only Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )

    profile = _create_profile_via_api(
        client,
        token,
        name="Protein Dense High kcal",
        target_kcal=2200,
        target_protein=130,
        target_fat=70,
        target_carbs=220,
    )
    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "profile_id": profile["id"],
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    lunch_slot = next(slot for slot in plan["slots"] if slot["slot_index"] == 0)
    assert Decimal(str(lunch_slot["servings_multiplier"])) <= Decimal("1.5")


def test_autogenerate_different_profiles_produce_different_multipliers_and_totals(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_profile_diff@example.com",
        username="autoplan_profile_diff",
    )

    lunch_light_food = create_food_via_api(
        client,
        token,
        name="Profile Diff Lunch Light",
        kcal="450.00",
        protein="25.00",
        fat="10.00",
        carbs="55.00",
    )
    lunch_heavy_food = create_food_via_api(
        client,
        token,
        name="Profile Diff Lunch Heavy",
        kcal="900.00",
        protein="40.00",
        fat="22.00",
        carbs="100.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Profile Diff Dinner",
        kcal="900.00",
        protein="45.00",
        fat="30.00",
        carbs="90.00",
    )
    lunch_light = _create_recipe_with_ingredient(
        client,
        token,
        name="Profile Diff Lunch Light",
        meal_types=["lunch"],
        food_id=lunch_light_food["id"],
    )
    lunch_heavy = _create_recipe_with_ingredient(
        client,
        token,
        name="Profile Diff Lunch Heavy",
        meal_types=["lunch"],
        food_id=lunch_heavy_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Profile Diff Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )

    low_kcal_profile = _create_profile_via_api(
        client,
        token,
        name="Low kcal profile",
        target_kcal=1400,
    )
    high_kcal_profile = _create_profile_via_api(
        client,
        token,
        name="High kcal profile",
        target_kcal=2200,
    )

    low_response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "profile_id": low_kcal_profile["id"],
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    high_response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-25",
            "days_count": 1,
            "meals_per_day": 2,
            "profile_id": high_kcal_profile["id"],
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert low_response.status_code == 201, low_response.text
    assert high_response.status_code == 201, high_response.text

    low_plan = low_response.json()
    high_plan = high_response.json()

    low_lunch_slot = next(slot for slot in low_plan["slots"] if slot["slot_index"] == 0)
    high_lunch_slot = next(slot for slot in high_plan["slots"] if slot["slot_index"] == 0)
    assert Decimal(str(high_lunch_slot["servings_multiplier"])) >= Decimal(str(low_lunch_slot["servings_multiplier"]))

    low_day_kcal = Decimal(str(low_plan["days"][0]["totals"]["kcal"]))
    high_day_kcal = Decimal(str(high_plan["days"][0]["totals"]["kcal"]))
    assert high_day_kcal > low_day_kcal


def test_autogenerate_happy_path_creates_plan_and_slots(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_happy@example.com",
        username="autoplan_happy",
    )

    breakfast_food = create_food_via_api(
        client,
        token,
        name="Autoplan Breakfast Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    lunch_food = create_food_via_api(
        client,
        token,
        name="Autoplan Lunch Food",
        kcal="150.00",
        protein="12.00",
        fat="6.00",
        carbs="18.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Autoplan Dinner Food",
        kcal="200.00",
        protein="20.00",
        fat="8.00",
        carbs="16.00",
    )

    _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Breakfast",
        meal_types=["breakfast"],
        food_id=breakfast_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Lunch",
        meal_types=["lunch"],
        food_id=lunch_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Dinner Backup",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 3,
            "meals_per_day": 3,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    assert len(plan["slots"]) == 9
    assert all(slot["recipe_id"] is not None for slot in plan["slots"])

    get_plan_response = client.get(
        f"/plans/{plan['id']}",
        headers=auth_headers(token),
    )
    assert get_plan_response.status_code == 200, get_plan_response.text
    get_plan_payload = get_plan_response.json()
    assert len(get_plan_payload["days"]) == 3
    assert any(day["totals"]["kcal"] != 0 for day in get_plan_payload["days"])

    shopping_response = client.get(
        f"/plans/{plan['id']}/shopping-list",
        headers=auth_headers(token),
    )
    assert shopping_response.status_code == 200, shopping_response.text
    shopping_payload = shopping_response.json()
    assert len(shopping_payload["items"]) > 0


def test_autogenerate_respects_meal_types_per_slot(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_meal_types@example.com",
        username="autoplan_meal_types",
    )

    breakfast_food = create_food_via_api(
        client,
        token,
        name="Meal Types Breakfast Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    lunch_food = create_food_via_api(
        client,
        token,
        name="Meal Types Lunch Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Meal Types Dinner Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    snack_food = create_food_via_api(
        client,
        token,
        name="Meal Types Snack Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )

    breakfast_recipe = _create_recipe_with_ingredient(
        client,
        token,
        name="Meal Types Breakfast",
        meal_types=["breakfast"],
        food_id=breakfast_food["id"],
    )
    lunch_recipe = _create_recipe_with_ingredient(
        client,
        token,
        name="Meal Types Lunch",
        meal_types=["lunch"],
        food_id=lunch_food["id"],
    )
    dinner_recipe = _create_recipe_with_ingredient(
        client,
        token,
        name="Meal Types Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )
    snack_recipe = _create_recipe_with_ingredient(
        client,
        token,
        name="Meal Types Snack",
        meal_types=["snack"],
        food_id=snack_food["id"],
    )

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 2,
            "meals_per_day": 4,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()

    meal_types_by_recipe_id = {
        breakfast_recipe["id"]: set(breakfast_recipe["meal_types"]),
        lunch_recipe["id"]: set(lunch_recipe["meal_types"]),
        dinner_recipe["id"]: set(dinner_recipe["meal_types"]),
        snack_recipe["id"]: set(snack_recipe["meal_types"]),
    }
    slot_meal_type_sequence = MEAL_SEQUENCE_BY_MEALS_PER_DAY[4]
    sorted_slots = sorted(plan["slots"], key=lambda slot: (slot["day_date"], slot["slot_index"]))
    for slot in sorted_slots:
        expected_meal_type = slot_meal_type_sequence[slot["slot_index"]]
        assert expected_meal_type in meal_types_by_recipe_id[slot["recipe_id"]]


def test_autogenerate_excludes_recipe_ids(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_excl_recipe@example.com",
        username="autoplan_excl_recipe",
    )

    food = create_food_via_api(
        client,
        token,
        name="Exclude Recipe Food",
        kcal="120.00",
        protein="11.00",
        fat="6.00",
        carbs="14.00",
    )
    excluded_breakfast = _create_recipe_with_ingredient(
        client,
        token,
        name="Exclude Recipe Breakfast",
        meal_types=["lunch"],
        food_id=food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Allowed Breakfast",
        meal_types=["lunch"],
        food_id=food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Allowed Dinner",
        meal_types=["dinner"],
        food_id=food["id"],
    )

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 2,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [excluded_breakfast["id"]],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    selected_recipe_ids = {slot["recipe_id"] for slot in plan["slots"]}
    assert excluded_breakfast["id"] not in selected_recipe_ids


def test_autogenerate_excludes_recipes_by_food_ids(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_excl_food@example.com",
        username="autoplan_excl_food",
    )

    allowed_food = create_food_via_api(
        client,
        token,
        name="Allowed Ingredient Food",
        kcal="90.00",
        protein="8.00",
        fat="4.00",
        carbs="10.00",
    )
    excluded_food = create_food_via_api(
        client,
        token,
        name="Excluded Ingredient Food",
        kcal="110.00",
        protein="9.00",
        fat="6.00",
        carbs="12.00",
    )

    excluded_recipe = _create_recipe_with_ingredient(
        client,
        token,
        name="Breakfast With Excluded Food",
        meal_types=["lunch"],
        food_id=excluded_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Breakfast Allowed Food",
        meal_types=["lunch"],
        food_id=allowed_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Dinner Allowed Food",
        meal_types=["dinner"],
        food_id=allowed_food["id"],
    )

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [excluded_food["id"]],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    selected_recipe_ids = {slot["recipe_id"] for slot in plan["slots"]}
    assert excluded_recipe["id"] not in selected_recipe_ids


def test_autogenerate_returns_422_when_meal_type_has_no_candidates(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_not_enough@example.com",
        username="autoplan_not_enough",
    )

    food = create_food_via_api(
        client,
        token,
        name="Not Enough Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Dinner Only",
        meal_types=["dinner"],
        food_id=food["id"],
    )

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-29",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 422, response.text
    assert "meal_type=lunch" in response.json()["detail"]
    assert "2026-03-29" in response.json()["detail"]


def test_autogenerate_repeat_penalty_avoids_adjacent_same_breakfast_when_possible(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_repeat_penalty@example.com",
        username="autoplan_repeat_penalty",
    )

    food = create_food_via_api(
        client,
        token,
        name="Repeat Penalty Food",
        kcal="130.00",
        protein="12.00",
        fat="7.00",
        carbs="15.00",
    )
    breakfast_a = _create_recipe_with_ingredient(
        client,
        token,
        name="Breakfast Candidate A",
        meal_types=["lunch"],
        food_id=food["id"],
    )
    breakfast_b = _create_recipe_with_ingredient(
        client,
        token,
        name="Breakfast Candidate B",
        meal_types=["lunch"],
        food_id=food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Dinner Candidate",
        meal_types=["dinner"],
        food_id=food["id"],
    )

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 3,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()

    breakfast_slot_recipe_ids = [
        slot["recipe_id"]
        for slot in sorted(plan["slots"], key=lambda slot: (slot["day_date"], slot["slot_index"]))
        if slot["slot_index"] == 0
    ]
    assert breakfast_slot_recipe_ids[0] == breakfast_a["id"]
    assert len(set(breakfast_slot_recipe_ids)) > 1
    assert all(
        breakfast_slot_recipe_ids[idx] != breakfast_slot_recipe_ids[idx + 1]
        for idx in range(len(breakfast_slot_recipe_ids) - 1)
    )
    assert breakfast_b["id"] in breakfast_slot_recipe_ids


def test_autogenerate_access_and_public_visibility_rules(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="autoplan_visibility_owner@example.com",
        username="autoplan_visibility_owner",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="autoplan_visibility_other@example.com",
        username="autoplan_visibility_other",
    )

    owner_food = create_food_via_api(
        client,
        owner_token,
        name="Owner Visibility Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    other_food = create_food_via_api(
        client,
        other_token,
        name="Other Visibility Food",
        kcal="120.00",
        protein="12.00",
        fat="6.00",
        carbs="18.00",
    )

    owner_breakfast = _create_recipe_with_ingredient(
        client,
        owner_token,
        name="Owner Breakfast Private",
        meal_types=["lunch"],
        food_id=owner_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        owner_token,
        name="Owner Dinner Private",
        meal_types=["dinner"],
        food_id=owner_food["id"],
    )

    other_private_breakfast = _create_recipe_with_ingredient(
        client,
        other_token,
        name="Other Breakfast Private",
        meal_types=["lunch"],
        food_id=other_food["id"],
    )
    other_public_breakfast = _create_recipe_with_ingredient(
        client,
        other_token,
        name="Other Breakfast Public",
        meal_types=["lunch"],
        food_id=other_food["id"],
    )
    publish_recipe_via_api(client, other_token, other_public_breakfast["id"])

    own_only_response = _post_autogenerate_plan(
        client,
        owner_token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert own_only_response.status_code == 201, own_only_response.text
    own_only_breakfast_recipe = next(
        slot["recipe_id"] for slot in own_only_response.json()["slots"] if slot["slot_index"] == 0
    )
    assert own_only_breakfast_recipe == owner_breakfast["id"]

    public_disabled_response = _post_autogenerate_plan(
        client,
        owner_token,
        {
            "start_date": "2026-03-25",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [owner_breakfast["id"]],
            "excluded_food_ids": [],
        },
    )
    assert public_disabled_response.status_code == 422, public_disabled_response.text

    public_enabled_response = _post_autogenerate_plan(
        client,
        owner_token,
        {
            "start_date": "2026-03-26",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [owner_breakfast["id"]],
            "excluded_food_ids": [],
        },
    )
    assert public_enabled_response.status_code == 201, public_enabled_response.text
    breakfast_recipe_id = next(
        slot["recipe_id"] for slot in public_enabled_response.json()["slots"] if slot["slot_index"] == 0
    )
    assert breakfast_recipe_id == other_public_breakfast["id"]
    assert breakfast_recipe_id != other_private_breakfast["id"]


def test_autogenerate_does_not_use_withdrawn_public_recipe(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="autoplan_withdrawn_owner@example.com",
        username="autoplan_withdrawn_owner",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="autoplan_withdrawn_other@example.com",
        username="autoplan_withdrawn_other",
    )

    owner_food = create_food_via_api(
        client,
        owner_token,
        name="Autoplan Withdrawn Owner Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    other_food = create_food_via_api(
        client,
        other_token,
        name="Autoplan Withdrawn Other Food",
        kcal="120.00",
        protein="12.00",
        fat="6.00",
        carbs="18.00",
    )

    owner_breakfast = _create_recipe_with_ingredient(
        client,
        owner_token,
        name="Autoplan Withdrawn Owner Breakfast",
        meal_types=["lunch"],
        food_id=owner_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        owner_token,
        name="Autoplan Withdrawn Owner Dinner",
        meal_types=["dinner"],
        food_id=owner_food["id"],
    )

    withdrawn_candidate = _create_recipe_with_ingredient(
        client,
        other_token,
        name="Autoplan Withdrawn Public Breakfast",
        meal_types=["lunch"],
        food_id=other_food["id"],
    )
    publish_recipe_via_api(client, other_token, withdrawn_candidate["id"])
    withdraw_recipe_via_api(client, other_token, withdrawn_candidate["id"])

    response = _post_autogenerate_plan(
        client,
        owner_token,
        {
            "start_date": "2026-03-27",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [owner_breakfast["id"]],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 422, response.text


def test_autogenerate_female_2220_with_4_meals_remains_reasonable(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
    finally:
        db.close()

    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_female_2220_4_meals@example.com",
        username="autoplan_female_2220_4_meals",
    )
    profile = _create_profile_via_api(
        client,
        token,
        name="Female 2220 / 4 meals",
        target_kcal=2220,
        target_protein=120,
        target_fat=60,
        target_carbs=300,
    )
    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-01",
            "days_count": 7,
            "meals_per_day": 4,
            "profile_id": profile["id"],
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()

    extreme_day_signatures: list[tuple[str, str, str, str]] = []
    for day in plan["days"]:
        kcal = Decimal(str(day["totals"]["kcal"]))
        protein = Decimal(str(day["totals"]["protein"]))
        fat = Decimal(str(day["totals"]["fat"]))
        carbs = Decimal(str(day["totals"]["carbs"]))
        assert kcal <= Decimal("2600")
        assert kcal >= Decimal("1700")
        assert fat <= Decimal("87")
        assert carbs >= Decimal("210")

        if (
            kcal > Decimal("2220") * Decimal("1.12")
            and protein > Decimal("120") * Decimal("1.25")
            and fat > Decimal("60") * Decimal("1.25")
        ):
            extreme_day_signatures.append(
                (
                    str(day["totals"]["kcal"]),
                    str(day["totals"]["protein"]),
                    str(day["totals"]["fat"]),
                    str(day["totals"]["carbs"]),
                )
            )

    assert len(extreme_day_signatures) <= 1
    assert len(extreme_day_signatures) == len(set(extreme_day_signatures))


def test_autogenerate_female_2220_with_5_meals_avoids_extreme_day_overshoot(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
    finally:
        db.close()

    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_female_2220_5_meals@example.com",
        username="autoplan_female_2220_5_meals",
    )
    profile = _create_profile_via_api(
        client,
        token,
        name="Female 2220 / 5 meals",
        target_kcal=2220,
        target_protein=120,
        target_fat=60,
        target_carbs=300,
    )
    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-01",
            "days_count": 7,
            "meals_per_day": 5,
            "profile_id": profile["id"],
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()

    weights = SLOT_WEIGHTS_BY_MEALS_PER_DAY[5]
    meal_sequence = MEAL_SEQUENCE_BY_MEALS_PER_DAY[5]
    slots_by_day: dict[str, list[dict]] = {}
    for slot in plan["slots"]:
        slots_by_day.setdefault(slot["day_date"], []).append(slot)
    for day_slots in slots_by_day.values():
        day_slots.sort(key=lambda item: item["slot_index"])

    for day in plan["days"]:
        kcal = Decimal(str(day["totals"]["kcal"]))
        fat = Decimal(str(day["totals"]["fat"]))
        assert kcal <= Decimal("2580")
        assert fat <= Decimal("84")

        huge_breakfast_snack_count = 0
        day_slots = slots_by_day[day["date"]]
        for slot in day_slots:
            slot_index = slot["slot_index"]
            meal_type = meal_sequence[slot_index]
            if meal_type not in {"breakfast", "snack"}:
                continue

            slot_target_kcal = Decimal("2220") * weights[slot_index]
            slot_kcal = Decimal(str(slot["slot_kcal"]))
            multiplier = Decimal(str(slot["servings_multiplier"]))
            if multiplier >= Decimal("2.0") and slot_kcal > slot_target_kcal * Decimal("1.50"):
                huge_breakfast_snack_count += 1

        assert huge_breakfast_snack_count < 2


def test_autogenerate_male_3530_controls_fat_and_keeps_carbs_closer_to_target(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
    finally:
        db.close()

    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_male_3530_guardrails@example.com",
        username="autoplan_male_3530_guardrails",
    )
    profile = _create_profile_via_api(
        client,
        token,
        name="Male 3530",
        target_kcal=3530,
        target_protein=180,
        target_fat=90,
        target_carbs=500,
    )
    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-01",
            "days_count": 7,
            "meals_per_day": 5,
            "profile_id": profile["id"],
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()

    fat_above_130 = 0
    carbs_below_390 = 0
    protein_high_and_carbs_low = 0
    for day in plan["days"]:
        kcal = Decimal(str(day["totals"]["kcal"]))
        protein = Decimal(str(day["totals"]["protein"]))
        fat = Decimal(str(day["totals"]["fat"]))
        carbs = Decimal(str(day["totals"]["carbs"]))
        assert kcal >= Decimal("3000")
        assert kcal <= Decimal("4060")
        if fat > Decimal("130"):
            fat_above_130 += 1
        if carbs < Decimal("390"):
            carbs_below_390 += 1
        if protein > Decimal("180") * Decimal("1.18") and carbs < Decimal("500") * Decimal("0.82"):
            protein_high_and_carbs_low += 1

    assert fat_above_130 <= 1
    assert carbs_below_390 <= 1
    assert protein_high_and_carbs_low <= 1


def test_autogenerate_penalizes_repeated_day_patterns_when_alternatives_exist(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_day_pattern_penalty@example.com",
        username="autoplan_day_pattern_penalty",
    )

    lunch_food = create_food_via_api(
        client,
        token,
        name="Day Pattern Lunch Food",
        kcal="520.00",
        protein="30.00",
        fat="14.00",
        carbs="62.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Day Pattern Dinner Food",
        kcal="700.00",
        protein="34.00",
        fat="20.00",
        carbs="84.00",
    )
    for suffix in ["A", "B", "C"]:
        _create_recipe_with_ingredient(
            client,
            token,
            name=f"Day Pattern Lunch {suffix}",
            meal_types=["lunch"],
            food_id=lunch_food["id"],
        )
        _create_recipe_with_ingredient(
            client,
            token,
            name=f"Day Pattern Dinner {suffix}",
            meal_types=["dinner"],
            food_id=dinner_food["id"],
        )

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-04",
            "days_count": 6,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    plan = response.json()

    slots_by_day: dict[str, list[dict]] = {}
    for slot in plan["slots"]:
        slots_by_day.setdefault(slot["day_date"], []).append(slot)
    day_patterns = []
    for day_date, day_slots in sorted(slots_by_day.items(), key=lambda item: item[0]):
        ordered = sorted(day_slots, key=lambda item: item["slot_index"])
        day_patterns.append((day_date, tuple(slot["recipe_id"] for slot in ordered)))

    repeated_patterns = len(day_patterns) - len({pattern for _, pattern in day_patterns})
    assert repeated_patterns <= 1


def test_autogenerate_seeded_pool_remains_deterministic_for_same_input(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
    finally:
        db.close()

    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_seeded_deterministic@example.com",
        username="autoplan_seeded_deterministic",
    )
    profile = _create_profile_via_api(
        client,
        token,
        name="Deterministic 2220/5",
        target_kcal=2220,
        target_protein=120,
        target_fat=60,
        target_carbs=300,
    )

    first_response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-02",
            "days_count": 7,
            "meals_per_day": 5,
            "profile_id": profile["id"],
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    second_response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-02",
            "days_count": 7,
            "meals_per_day": 5,
            "profile_id": profile["id"],
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert first_response.status_code == 201, first_response.text
    assert second_response.status_code == 201, second_response.text

    first_plan = first_response.json()
    second_plan = second_response.json()
    first_signature = [
        (slot["day_date"], slot["slot_index"], slot["recipe_id"], str(slot["servings_multiplier"]))
        for slot in sorted(first_plan["slots"], key=lambda item: (item["day_date"], item["slot_index"], item["id"]))
    ]
    second_signature = [
        (slot["day_date"], slot["slot_index"], slot["recipe_id"], str(slot["servings_multiplier"]))
        for slot in sorted(second_plan["slots"], key=lambda item: (item["day_date"], item["slot_index"], item["id"]))
    ]
    assert first_signature == second_signature


def test_autogenerate_is_deterministic_and_uses_stable_tie_break(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_deterministic_tie_break@example.com",
        username="autoplan_deterministic_tie_break",
    )

    lunch_food = create_food_via_api(
        client,
        token,
        name="Autoplan Deterministic Lunch Food",
        kcal="500.00",
        protein="30.00",
        fat="15.00",
        carbs="55.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Autoplan Deterministic Dinner Food",
        kcal="700.00",
        protein="38.00",
        fat="22.00",
        carbs="78.00",
    )

    first_lunch = _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Deterministic Lunch A",
        meal_types=["lunch"],
        food_id=lunch_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Deterministic Lunch B",
        meal_types=["lunch"],
        food_id=lunch_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Deterministic Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )

    first_response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-29",
            "days_count": 2,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    second_response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-29",
            "days_count": 2,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert first_response.status_code == 201, first_response.text
    assert second_response.status_code == 201, second_response.text

    first_plan = first_response.json()
    second_plan = second_response.json()

    first_plan_slots = sorted(first_plan["slots"], key=lambda slot: (slot["day_date"], slot["slot_index"], slot["id"]))
    second_plan_slots = sorted(
        second_plan["slots"],
        key=lambda slot: (slot["day_date"], slot["slot_index"], slot["id"]),
    )

    first_signature = [(slot["slot_index"], slot["recipe_id"], str(slot["servings_multiplier"])) for slot in first_plan_slots]
    second_signature = [
        (slot["slot_index"], slot["recipe_id"], str(slot["servings_multiplier"])) for slot in second_plan_slots
    ]
    assert first_signature == second_signature

    # Both lunch candidates are nutritionally identical, so deterministic tie-break should pick the smallest id.
    first_lunch_slot = next(slot for slot in first_plan_slots if slot["slot_index"] == 0)
    assert first_lunch_slot["recipe_id"] == first_lunch["id"]


def test_autogenerate_respects_profile_excluded_food_ids(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_profile_excluded_food@example.com",
        username="autoplan_profile_excluded_food",
    )

    excluded_food = create_food_via_api(
        client,
        token,
        name="Autoplan Excluded Food",
        kcal="300.00",
        protein="22.00",
        fat="9.00",
        carbs="30.00",
    )
    allowed_food = create_food_via_api(
        client,
        token,
        name="Autoplan Allowed Food",
        kcal="300.00",
        protein="22.00",
        fat="9.00",
        carbs="30.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Autoplan Dinner Food",
        kcal="600.00",
        protein="35.00",
        fat="18.00",
        carbs="70.00",
    )

    excluded_lunch = _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Excluded Lunch",
        meal_types=["lunch"],
        food_id=excluded_food["id"],
    )
    allowed_lunch = _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Allowed Lunch",
        meal_types=["lunch"],
        food_id=allowed_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Excluded Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )

    profiles = _list_profiles(client, token)
    default_profile_id = profiles[0]["id"]
    _patch_profile_via_api(
        client,
        token,
        default_profile_id,
        {"excluded_food_ids": [excluded_food["id"]]},
    )

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-10",
            "days_count": 1,
            "meals_per_day": 2,
            "profile_id": default_profile_id,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    slots = sorted(response.json()["slots"], key=lambda slot: (slot["day_date"], slot["slot_index"], slot["id"]))
    lunch_slot = next(slot for slot in slots if slot["slot_index"] == 0)
    assert lunch_slot["recipe_id"] == allowed_lunch["id"]
    assert lunch_slot["recipe_id"] != excluded_lunch["id"]


def test_autogenerate_applies_request_max_cook_time_minutes(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_request_max_cook_time@example.com",
        username="autoplan_request_max_cook_time",
    )

    lunch_food = create_food_via_api(
        client,
        token,
        name="Autoplan Cook Time Lunch Food",
        kcal="420.00",
        protein="26.00",
        fat="12.00",
        carbs="50.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Autoplan Cook Time Dinner Food",
        kcal="680.00",
        protein="38.00",
        fat="22.00",
        carbs="74.00",
    )

    slow_lunch = _create_recipe_with_ingredient_and_cook_time(
        client,
        token,
        name="Autoplan Slow Lunch",
        meal_types=["lunch"],
        food_id=lunch_food["id"],
        cook_time_minutes=55,
    )
    fast_lunch = _create_recipe_with_ingredient_and_cook_time(
        client,
        token,
        name="Autoplan Fast Lunch",
        meal_types=["lunch"],
        food_id=lunch_food["id"],
        cook_time_minutes=20,
    )
    _create_recipe_with_ingredient_and_cook_time(
        client,
        token,
        name="Autoplan Cook Time Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
        cook_time_minutes=30,
    )

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-12",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
            "max_cook_time_minutes": 30,
        },
    )
    assert response.status_code == 201, response.text
    slots = sorted(response.json()["slots"], key=lambda slot: (slot["day_date"], slot["slot_index"], slot["id"]))
    lunch_slot = next(slot for slot in slots if slot["slot_index"] == 0)
    assert lunch_slot["recipe_id"] == fast_lunch["id"]
    assert lunch_slot["recipe_id"] != slow_lunch["id"]


def test_autogenerate_prefers_profile_preferred_foods(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_profile_preferred_food@example.com",
        username="autoplan_profile_preferred_food",
    )

    non_preferred_food = create_food_via_api(
        client,
        token,
        name="Autoplan Non Preferred Food",
        kcal="390.00",
        protein="25.00",
        fat="11.00",
        carbs="46.00",
    )
    preferred_food = create_food_via_api(
        client,
        token,
        name="Autoplan Preferred Food",
        kcal="390.00",
        protein="25.00",
        fat="11.00",
        carbs="46.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Autoplan Preferred Dinner Food",
        kcal="640.00",
        protein="36.00",
        fat="19.00",
        carbs="70.00",
    )

    _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Lunch Without Preference",
        meal_types=["lunch"],
        food_id=non_preferred_food["id"],
    )
    preferred_recipe = _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Lunch With Preference",
        meal_types=["lunch"],
        food_id=preferred_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Preferred Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )

    profiles = _list_profiles(client, token)
    default_profile_id = profiles[0]["id"]
    _patch_profile_via_api(
        client,
        token,
        default_profile_id,
        {"preferred_food_ids": [preferred_food["id"]]},
    )

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-14",
            "days_count": 1,
            "meals_per_day": 2,
            "profile_id": default_profile_id,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    slots = sorted(response.json()["slots"], key=lambda slot: (slot["day_date"], slot["slot_index"], slot["id"]))
    lunch_slot = next(slot for slot in slots if slot["slot_index"] == 0)
    assert lunch_slot["recipe_id"] == preferred_recipe["id"]


def test_autogenerate_prefers_profile_preferred_categories_when_other_factors_equal(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_profile_preferred_category@example.com",
        username="autoplan_profile_preferred_category",
    )

    preferred_food_response = client.post(
        "/foods",
        headers=auth_headers(token),
        json={
            "name": "Autoplan Preferred Category Food",
            "kcal": "380.00",
            "protein": "24.00",
            "fat": "10.00",
            "carbs": "45.00",
            "category": "meat_fish",
        },
    )
    assert preferred_food_response.status_code == 201, preferred_food_response.text
    preferred_category_food = preferred_food_response.json()

    neutral_food_response = client.post(
        "/foods",
        headers=auth_headers(token),
        json={
            "name": "Autoplan Neutral Category Food",
            "kcal": "380.00",
            "protein": "24.00",
            "fat": "10.00",
            "carbs": "45.00",
            "category": "vegetables",
        },
    )
    assert neutral_food_response.status_code == 201, neutral_food_response.text
    neutral_food = neutral_food_response.json()

    dinner_food = create_food_via_api(
        client,
        token,
        name="Autoplan Preferred Category Dinner Food",
        kcal="640.00",
        protein="35.00",
        fat="19.00",
        carbs="72.00",
    )

    preferred_category_recipe = _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Lunch Preferred Category",
        meal_types=["lunch"],
        food_id=preferred_category_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Lunch Neutral Category",
        meal_types=["lunch"],
        food_id=neutral_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Autoplan Preferred Category Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )

    profiles = _list_profiles(client, token)
    default_profile_id = profiles[0]["id"]
    _patch_profile_via_api(
        client,
        token,
        default_profile_id,
        {"preferred_categories": ["meat_fish"]},
    )

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-16",
            "days_count": 1,
            "meals_per_day": 2,
            "profile_id": default_profile_id,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    slots = sorted(response.json()["slots"], key=lambda slot: (slot["day_date"], slot["slot_index"], slot["id"]))
    lunch_slot = next(slot for slot in slots if slot["slot_index"] == 0)
    assert lunch_slot["recipe_id"] == preferred_category_recipe["id"]


def test_autogenerate_batch_cooking_reuses_recipe_for_two_days(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_batch_cooking@example.com",
        username="autoplan_batch_cooking",
    )

    lunch_food_a = create_food_via_api(
        client,
        token,
        name="Autoplan Batch Lunch A",
        kcal="450.00",
        protein="28.00",
        fat="14.00",
        carbs="52.00",
    )
    lunch_food_b = create_food_via_api(
        client,
        token,
        name="Autoplan Batch Lunch B",
        kcal="460.00",
        protein="29.00",
        fat="14.00",
        carbs="53.00",
    )
    dinner_food_a = create_food_via_api(
        client,
        token,
        name="Autoplan Batch Dinner A",
        kcal="680.00",
        protein="37.00",
        fat="21.00",
        carbs="74.00",
    )
    dinner_food_b = create_food_via_api(
        client,
        token,
        name="Autoplan Batch Dinner B",
        kcal="690.00",
        protein="38.00",
        fat="22.00",
        carbs="75.00",
    )

    _create_recipe_with_ingredient(client, token, name="Autoplan Batch Lunch Recipe A", meal_types=["lunch"], food_id=lunch_food_a["id"])
    _create_recipe_with_ingredient(client, token, name="Autoplan Batch Lunch Recipe B", meal_types=["lunch"], food_id=lunch_food_b["id"])
    _create_recipe_with_ingredient(client, token, name="Autoplan Batch Dinner Recipe A", meal_types=["dinner"], food_id=dinner_food_a["id"])
    _create_recipe_with_ingredient(client, token, name="Autoplan Batch Dinner Recipe B", meal_types=["dinner"], food_id=dinner_food_b["id"])

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-20",
            "days_count": 3,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
            "batch_cooking": {
                "lunch": 2,
                "dinner": 2,
            },
        },
    )
    assert response.status_code == 201, response.text
    slots = sorted(response.json()["slots"], key=lambda slot: (slot["day_date"], slot["slot_index"], slot["id"]))

    day1_lunch = next(slot for slot in slots if slot["day_date"] == "2026-04-20" and slot["slot_index"] == 0)
    day2_lunch = next(slot for slot in slots if slot["day_date"] == "2026-04-21" and slot["slot_index"] == 0)
    day1_dinner = next(slot for slot in slots if slot["day_date"] == "2026-04-20" and slot["slot_index"] == 1)
    day2_dinner = next(slot for slot in slots if slot["day_date"] == "2026-04-21" and slot["slot_index"] == 1)

    assert day1_lunch["recipe_id"] == day2_lunch["recipe_id"]
    assert day1_dinner["recipe_id"] == day2_dinner["recipe_id"]


def test_autogenerate_batch_cooking_reuses_dinner_for_three_day_window(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_batch_cooking_three_days@example.com",
        username="autoplan_batch_cooking_three_days",
    )

    lunch_food = create_food_via_api(
        client,
        token,
        name="Autoplan Batch3 Lunch Food",
        kcal="420.00",
        protein="24.00",
        fat="10.00",
        carbs="48.00",
    )
    dinner_food_a = create_food_via_api(
        client,
        token,
        name="Autoplan Batch3 Dinner Food A",
        kcal="650.00",
        protein="34.00",
        fat="20.00",
        carbs="70.00",
    )
    dinner_food_b = create_food_via_api(
        client,
        token,
        name="Autoplan Batch3 Dinner Food B",
        kcal="660.00",
        protein="35.00",
        fat="20.00",
        carbs="71.00",
    )

    _create_recipe_with_ingredient(client, token, name="Autoplan Batch3 Lunch", meal_types=["lunch"], food_id=lunch_food["id"])
    _create_recipe_with_ingredient(client, token, name="Autoplan Batch3 Dinner A", meal_types=["dinner"], food_id=dinner_food_a["id"])
    _create_recipe_with_ingredient(client, token, name="Autoplan Batch3 Dinner B", meal_types=["dinner"], food_id=dinner_food_b["id"])

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-24",
            "days_count": 5,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
            "batch_cooking": {"dinner": 3},
        },
    )
    assert response.status_code == 201, response.text
    slots = sorted(response.json()["slots"], key=lambda slot: (slot["day_date"], slot["slot_index"], slot["id"]))

    day1_dinner = next(slot for slot in slots if slot["day_date"] == "2026-04-24" and slot["slot_index"] == 1)
    day2_dinner = next(slot for slot in slots if slot["day_date"] == "2026-04-25" and slot["slot_index"] == 1)
    day3_dinner = next(slot for slot in slots if slot["day_date"] == "2026-04-26" and slot["slot_index"] == 1)
    day4_dinner = next(slot for slot in slots if slot["day_date"] == "2026-04-27" and slot["slot_index"] == 1)
    day5_dinner = next(slot for slot in slots if slot["day_date"] == "2026-04-28" and slot["slot_index"] == 1)

    assert day1_dinner["recipe_id"] == day2_dinner["recipe_id"] == day3_dinner["recipe_id"]
    assert day4_dinner["recipe_id"] == day5_dinner["recipe_id"]


def test_autogenerate_batch_cooking_missing_meal_type_equals_explicit_one(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_batch_cooking_missing_equals_one@example.com",
        username="autoplan_batch_cooking_missing_equals_one",
    )

    lunch_food_a = create_food_via_api(
        client,
        token,
        name="Autoplan Batch One Lunch A",
        kcal="470.00",
        protein="27.00",
        fat="14.00",
        carbs="55.00",
    )
    lunch_food_b = create_food_via_api(
        client,
        token,
        name="Autoplan Batch One Lunch B",
        kcal="475.00",
        protein="27.00",
        fat="14.00",
        carbs="55.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Autoplan Batch One Dinner",
        kcal="660.00",
        protein="35.00",
        fat="21.00",
        carbs="74.00",
    )

    _create_recipe_with_ingredient(client, token, name="Autoplan Batch One Lunch Recipe A", meal_types=["lunch"], food_id=lunch_food_a["id"])
    _create_recipe_with_ingredient(client, token, name="Autoplan Batch One Lunch Recipe B", meal_types=["lunch"], food_id=lunch_food_b["id"])
    _create_recipe_with_ingredient(client, token, name="Autoplan Batch One Dinner Recipe", meal_types=["dinner"], food_id=dinner_food["id"])

    with_missing = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-29",
            "days_count": 3,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
            "batch_cooking": {},
        },
    )
    with_explicit_one = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-29",
            "days_count": 3,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
            "batch_cooking": {"lunch": 1, "dinner": 1},
        },
    )
    assert with_missing.status_code == 201, with_missing.text
    assert with_explicit_one.status_code == 201, with_explicit_one.text

    missing_signature = [
        (slot["day_date"], slot["slot_index"], slot["recipe_id"], str(slot["servings_multiplier"]))
        for slot in sorted(with_missing.json()["slots"], key=lambda item: (item["day_date"], item["slot_index"], item["id"]))
    ]
    explicit_signature = [
        (slot["day_date"], slot["slot_index"], slot["recipe_id"], str(slot["servings_multiplier"]))
        for slot in sorted(
            with_explicit_one.json()["slots"],
            key=lambda item: (item["day_date"], item["slot_index"], item["id"]),
        )
    ]
    assert missing_signature == explicit_signature


def test_autogenerate_batch_cooking_validation_rejects_out_of_range_values(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_batch_cooking_invalid_values@example.com",
        username="autoplan_batch_cooking_invalid_values",
    )

    bad_zero_response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-30",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
            "batch_cooking": {"lunch": 0},
        },
    )
    bad_high_response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-30",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
            "batch_cooking": {"dinner": 4},
        },
    )
    bad_key_response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-04-30",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
            "batch_cooking": {"brunch": 2},
        },
    )

    assert bad_zero_response.status_code == 422, bad_zero_response.text
    assert bad_high_response.status_code == 422, bad_high_response.text
    assert bad_key_response.status_code == 422, bad_key_response.text
    assert any("batch_cooking" in ".".join(str(item) for item in err["loc"]) for err in bad_zero_response.json().get("detail", []))
    assert any("batch_cooking" in ".".join(str(item) for item in err["loc"]) for err in bad_high_response.json().get("detail", []))
    assert any("batch_cooking" in ".".join(str(item) for item in err["loc"]) for err in bad_key_response.json().get("detail", []))


def test_autogenerate_batch_repeat_not_defeated_by_repeat_penalty(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_batch_repeat_penalty_guard@example.com",
        username="autoplan_batch_repeat_penalty_guard",
    )

    lunch_food_a = create_food_via_api(
        client,
        token,
        name="Autoplan Batch Penalty Lunch A",
        kcal="430.00",
        protein="26.00",
        fat="12.00",
        carbs="49.00",
    )
    lunch_food_b = create_food_via_api(
        client,
        token,
        name="Autoplan Batch Penalty Lunch B",
        kcal="435.00",
        protein="26.00",
        fat="12.00",
        carbs="50.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Autoplan Batch Penalty Dinner",
        kcal="640.00",
        protein="34.00",
        fat="19.00",
        carbs="71.00",
    )

    _create_recipe_with_ingredient(client, token, name="Autoplan Batch Penalty Lunch Recipe A", meal_types=["lunch"], food_id=lunch_food_a["id"])
    _create_recipe_with_ingredient(client, token, name="Autoplan Batch Penalty Lunch Recipe B", meal_types=["lunch"], food_id=lunch_food_b["id"])
    _create_recipe_with_ingredient(client, token, name="Autoplan Batch Penalty Dinner Recipe", meal_types=["dinner"], food_id=dinner_food["id"])

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-05-01",
            "days_count": 4,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
            "batch_cooking": {"lunch": 2},
        },
    )
    assert response.status_code == 201, response.text
    slots = sorted(response.json()["slots"], key=lambda slot: (slot["day_date"], slot["slot_index"], slot["id"]))
    lunch_day1 = next(slot for slot in slots if slot["day_date"] == "2026-05-01" and slot["slot_index"] == 0)
    lunch_day2 = next(slot for slot in slots if slot["day_date"] == "2026-05-02" and slot["slot_index"] == 0)
    lunch_day3 = next(slot for slot in slots if slot["day_date"] == "2026-05-03" and slot["slot_index"] == 0)
    lunch_day4 = next(slot for slot in slots if slot["day_date"] == "2026-05-04" and slot["slot_index"] == 0)

    assert lunch_day1["recipe_id"] == lunch_day2["recipe_id"]
    assert lunch_day3["recipe_id"] == lunch_day4["recipe_id"]


def _has_identical_run(values: list[int], run_length: int) -> bool:
    if run_length <= 1:
        return len(values) > 0
    streak = 1
    for idx in range(1, len(values)):
        if values[idx] == values[idx - 1]:
            streak += 1
            if streak >= run_length:
                return True
        else:
            streak = 1
    return False


def test_autogenerate_max_cook_time_20_generates_week_plan_with_demo_pool(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
    finally:
        db.close()

    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_demo_fast_pool_20@example.com",
        username="autoplan_demo_fast_pool_20",
    )
    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-05-05",
            "days_count": 7,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
            "max_cook_time_minutes": 20,
        },
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["slots"]) == 14


def test_autogenerate_batch_one_lunch_avoids_four_identical_days_when_alternatives_exist(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_batch_one_lunch_diversity@example.com",
        username="autoplan_batch_one_lunch_diversity",
    )

    for idx in range(1, 5):
        lunch_food = create_food_via_api(
            client,
            token,
            name=f"Autoplan Batch1 Lunch Diversity Food {idx}",
            kcal="440.00",
            protein="28.00",
            fat="12.00",
            carbs="50.00",
        )
        _create_recipe_with_ingredient(
            client,
            token,
            name=f"Autoplan Batch1 Lunch Diversity Recipe {idx}",
            meal_types=["lunch"],
            food_id=lunch_food["id"],
        )

    for idx in range(1, 3):
        dinner_food = create_food_via_api(
            client,
            token,
            name=f"Autoplan Batch1 Lunch Diversity Dinner Food {idx}",
            kcal="650.00",
            protein="34.00",
            fat="20.00",
            carbs="72.00",
        )
        _create_recipe_with_ingredient(
            client,
            token,
            name=f"Autoplan Batch1 Lunch Diversity Dinner Recipe {idx}",
            meal_types=["dinner"],
            food_id=dinner_food["id"],
        )

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-05-12",
            "days_count": 7,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
            "batch_cooking": {"lunch": 1},
        },
    )
    assert response.status_code == 201, response.text
    slots = sorted(response.json()["slots"], key=lambda slot: (slot["day_date"], slot["slot_index"], slot["id"]))
    lunch_recipe_ids = [slot["recipe_id"] for slot in slots if slot["slot_index"] == 0]
    assert not _has_identical_run(lunch_recipe_ids, 4)


def test_autogenerate_batch_one_dinner_avoids_four_identical_days_when_alternatives_exist(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_batch_one_dinner_diversity@example.com",
        username="autoplan_batch_one_dinner_diversity",
    )

    for idx in range(1, 5):
        dinner_food = create_food_via_api(
            client,
            token,
            name=f"Autoplan Batch1 Dinner Diversity Food {idx}",
            kcal="660.00",
            protein="35.00",
            fat="21.00",
            carbs="73.00",
        )
        _create_recipe_with_ingredient(
            client,
            token,
            name=f"Autoplan Batch1 Dinner Diversity Recipe {idx}",
            meal_types=["dinner"],
            food_id=dinner_food["id"],
        )

    for idx in range(1, 3):
        lunch_food = create_food_via_api(
            client,
            token,
            name=f"Autoplan Batch1 Dinner Diversity Lunch Food {idx}",
            kcal="430.00",
            protein="27.00",
            fat="11.00",
            carbs="48.00",
        )
        _create_recipe_with_ingredient(
            client,
            token,
            name=f"Autoplan Batch1 Dinner Diversity Lunch Recipe {idx}",
            meal_types=["lunch"],
            food_id=lunch_food["id"],
        )

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-05-20",
            "days_count": 7,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
            "batch_cooking": {"dinner": 1},
        },
    )
    assert response.status_code == 201, response.text
    slots = sorted(response.json()["slots"], key=lambda slot: (slot["day_date"], slot["slot_index"], slot["id"]))
    dinner_recipe_ids = [slot["recipe_id"] for slot in slots if slot["slot_index"] == 1]
    assert not _has_identical_run(dinner_recipe_ids, 4)


def test_autogenerate_returns_friendly_422_when_fast_candidates_too_few_for_diversity(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="autoplan_fast_candidates_too_few@example.com",
        username="autoplan_fast_candidates_too_few",
    )

    for idx in range(1, 3):
        lunch_food = create_food_via_api(
            client,
            token,
            name=f"Autoplan Fast Few Lunch Food {idx}",
            kcal="420.00",
            protein="26.00",
            fat="11.00",
            carbs="49.00",
        )
        _create_recipe_with_ingredient_and_cook_time(
            client,
            token,
            name=f"Autoplan Fast Few Lunch Recipe {idx}",
            meal_types=["lunch"],
            food_id=lunch_food["id"],
            cook_time_minutes=20,
        )

    for idx in range(1, 3):
        dinner_food = create_food_via_api(
            client,
            token,
            name=f"Autoplan Fast Few Dinner Food {idx}",
            kcal="640.00",
            protein="34.00",
            fat="19.00",
            carbs="70.00",
        )
        _create_recipe_with_ingredient_and_cook_time(
            client,
            token,
            name=f"Autoplan Fast Few Dinner Recipe {idx}",
            meal_types=["dinner"],
            food_id=dinner_food["id"],
            cook_time_minutes=20,
        )

    response = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-05-26",
            "days_count": 7,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
            "max_cook_time_minutes": 20,
            "batch_cooking": {"lunch": 1, "dinner": 1},
        },
    )
    assert response.status_code == 422, response.text
    detail = response.json().get("detail")
    assert isinstance(detail, str)
    assert "Недостаточно быстрых рецептов для разнообразного плана" in detail
