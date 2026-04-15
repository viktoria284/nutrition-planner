from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

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
