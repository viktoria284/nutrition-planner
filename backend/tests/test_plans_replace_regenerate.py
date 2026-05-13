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
)


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


def _post_autogenerate_plan(client: TestClient, token: str, payload: dict) -> dict:
    response = client.post(
        "/plans/autogenerate",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _patch_plan_slot(
    client: TestClient,
    token: str,
    *,
    plan_id: int,
    slot_id: int,
    payload: dict,
) -> dict:
    response = client.patch(
        f"/plans/{plan_id}/slots/{slot_id}",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _replace_slot(
    client: TestClient,
    token: str,
    *,
    plan_id: int,
    slot_id: int,
    payload: dict | None = None,
):
    if payload is None:
        return client.post(
            f"/plans/{plan_id}/slots/{slot_id}/replace",
            headers=auth_headers(token),
        )
    return client.post(
        f"/plans/{plan_id}/slots/{slot_id}/replace",
        headers=auth_headers(token),
        json=payload,
    )


def _regenerate_day(
    client: TestClient,
    token: str,
    *,
    plan_id: int,
    day_date: str,
    payload: dict,
):
    return client.post(
        f"/plans/{plan_id}/days/{day_date}/regenerate",
        headers=auth_headers(token),
        json=payload,
    )


def _find_slot(plan_payload: dict, *, day_date: str, slot_index: int) -> dict:
    return next(
        slot for slot in plan_payload["slots"] if slot["day_date"] == day_date and slot["slot_index"] == slot_index
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


def _patch_profile_via_api(client: TestClient, token: str, profile_id: int, payload: dict) -> dict:
    response = client.patch(
        f"/profiles/{profile_id}",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_replace_slot_uses_plan_snapshot_targets_not_updated_profile(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="replace_snapshot_profile@example.com",
        username="replace_snapshot_profile",
    )

    lunch_low_food = create_food_via_api(
        client,
        token,
        name="Replace Snapshot Lunch Low",
        kcal="450.00",
        protein="30.00",
        fat="12.00",
        carbs="52.00",
    )
    lunch_high_food = create_food_via_api(
        client,
        token,
        name="Replace Snapshot Lunch High",
        kcal="900.00",
        protein="45.00",
        fat="28.00",
        carbs="95.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Replace Snapshot Dinner",
        kcal="900.00",
        protein="40.00",
        fat="30.00",
        carbs="90.00",
    )
    lunch_low = _create_recipe_with_ingredient(
        client, token, name="Replace Snapshot Lunch Low", meal_types=["lunch"], food_id=lunch_low_food["id"]
    )
    lunch_high = _create_recipe_with_ingredient(
        client, token, name="Replace Snapshot Lunch High", meal_types=["lunch"], food_id=lunch_high_food["id"]
    )
    _create_recipe_with_ingredient(
        client, token, name="Replace Snapshot Dinner", meal_types=["dinner"], food_id=dinner_food["id"]
    )

    profile = _create_profile_via_api(
        client,
        token,
        name="Snapshot profile",
        target_kcal=1400,
    )
    plan = _post_autogenerate_plan(
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
    assert plan["target_kcal"] == 1400
    lunch_slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)
    assert lunch_slot["recipe_id"] == lunch_low["id"]

    _patch_profile_via_api(
        client,
        token,
        profile["id"],
        payload={"target_kcal": 2400},
    )
    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=lunch_slot["id"],
        payload={"servings_multiplier": "1.8", "pinned": True},
    )

    replace_response = _replace_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=lunch_slot["id"],
        payload={"avoid_current_recipe": False},
    )
    assert replace_response.status_code == 200, replace_response.text
    replaced_slot = _find_slot(replace_response.json(), day_date="2026-03-24", slot_index=0)
    assert replaced_slot["recipe_id"] == lunch_high["id"]
    assert Decimal(str(replaced_slot["servings_multiplier"])) > Decimal("0")
    assert replaced_slot["pinned"] is True


def test_regenerate_day_uses_plan_snapshot_targets_not_updated_profile(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="regenerate_snapshot_profile@example.com",
        username="regenerate_snapshot_profile",
    )

    lunch_low_food = create_food_via_api(
        client,
        token,
        name="Regenerate Snapshot Lunch Low",
        kcal="450.00",
        protein="30.00",
        fat="12.00",
        carbs="52.00",
    )
    lunch_high_food = create_food_via_api(
        client,
        token,
        name="Regenerate Snapshot Lunch High",
        kcal="900.00",
        protein="45.00",
        fat="28.00",
        carbs="95.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Regenerate Snapshot Dinner",
        kcal="900.00",
        protein="40.00",
        fat="30.00",
        carbs="90.00",
    )
    lunch_low = _create_recipe_with_ingredient(
        client, token, name="Regenerate Snapshot Lunch Low", meal_types=["lunch"], food_id=lunch_low_food["id"]
    )
    _create_recipe_with_ingredient(
        client, token, name="Regenerate Snapshot Lunch High", meal_types=["lunch"], food_id=lunch_high_food["id"]
    )
    _create_recipe_with_ingredient(
        client, token, name="Regenerate Snapshot Dinner", meal_types=["dinner"], food_id=dinner_food["id"]
    )

    profile = _create_profile_via_api(
        client,
        token,
        name="Regenerate snapshot profile",
        target_kcal=1400,
    )
    plan = _post_autogenerate_plan(
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
    assert plan["target_kcal"] == 1400
    assert _find_slot(plan, day_date="2026-03-24", slot_index=0)["recipe_id"] == lunch_low["id"]

    _patch_profile_via_api(
        client,
        token,
        profile["id"],
        payload={"target_kcal": 2400},
    )

    regenerate_response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-03-24",
        payload={},
    )
    assert regenerate_response.status_code == 200, regenerate_response.text
    regenerated_plan = regenerate_response.json()
    regenerated_day_kcal = Decimal(str(regenerated_plan["days"][0]["totals"]["kcal"]))
    assert abs(regenerated_day_kcal - Decimal("1400")) < abs(regenerated_day_kcal - Decimal("2400"))


def test_replace_and_regenerate_can_recalculate_servings_multiplier(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="replace_regen_multiplier_aware@example.com",
        username="replace_regen_multiplier_aware",
    )

    lunch_food = create_food_via_api(
        client,
        token,
        name="Multiplier Aware Lunch Food",
        kcal="300.00",
        protein="20.00",
        fat="10.00",
        carbs="35.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Multiplier Aware Dinner Food",
        kcal="400.00",
        protein="25.00",
        fat="14.00",
        carbs="42.00",
    )
    lunch_recipe = _create_recipe_with_ingredient(
        client, token, name="Multiplier Aware Lunch", meal_types=["lunch"], food_id=lunch_food["id"]
    )
    _create_recipe_with_ingredient(
        client, token, name="Multiplier Aware Lunch Alt", meal_types=["lunch"], food_id=lunch_food["id"]
    )
    _create_recipe_with_ingredient(
        client, token, name="Multiplier Aware Dinner", meal_types=["dinner"], food_id=dinner_food["id"]
    )

    profile = _create_profile_via_api(
        client,
        token,
        name="Multiplier aware profile",
        target_kcal=2200,
    )
    plan = _post_autogenerate_plan(
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
    lunch_slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)
    assert lunch_slot["recipe_id"] == lunch_recipe["id"]

    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=lunch_slot["id"],
        payload={"servings_multiplier": "0.75"},
    )

    replace_response = _replace_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=lunch_slot["id"],
        payload={"avoid_current_recipe": False},
    )
    assert replace_response.status_code == 200, replace_response.text
    replaced_lunch_slot = _find_slot(replace_response.json(), day_date="2026-03-24", slot_index=0)
    assert replaced_lunch_slot["recipe_id"] != lunch_recipe["id"]
    assert Decimal(str(replaced_lunch_slot["servings_multiplier"])) > Decimal("0.75")

    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=lunch_slot["id"],
        payload={"servings_multiplier": "0.75"},
    )

    regenerate_response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-03-24",
        payload={},
    )
    assert regenerate_response.status_code == 200, regenerate_response.text
    regenerated_lunch_slot = _find_slot(regenerate_response.json(), day_date="2026-03-24", slot_index=0)
    assert Decimal(str(regenerated_lunch_slot["servings_multiplier"])) > Decimal("0.75")


def test_replace_and_regenerate_apply_macro_guardrails_for_high_carb_profile(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="replace_regen_macro_guardrails@example.com",
        username="replace_regen_macro_guardrails",
    )

    protein_heavy_food = create_food_via_api(
        client,
        token,
        name="Replace Regen Protein Heavy Lunch Food",
        kcal="460.00",
        protein="62.00",
        fat="12.00",
        carbs="8.00",
    )
    carb_friendly_food = create_food_via_api(
        client,
        token,
        name="Replace Regen Carb Friendly Lunch Food",
        kcal="420.00",
        protein="18.00",
        fat="10.00",
        carbs="68.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Replace Regen Dinner Food",
        kcal="820.00",
        protein="30.00",
        fat="25.00",
        carbs="96.00",
    )
    protein_heavy_lunch = _create_recipe_with_ingredient(
        client,
        token,
        name="Replace Regen Protein Heavy Lunch",
        meal_types=["lunch"],
        food_id=protein_heavy_food["id"],
    )
    carb_friendly_lunch = _create_recipe_with_ingredient(
        client,
        token,
        name="Replace Regen Carb Friendly Lunch",
        meal_types=["lunch"],
        food_id=carb_friendly_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Replace Regen Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )

    profile = _create_profile_via_api(
        client,
        token,
        name="Replace Regen Macro Guardrails Profile",
        target_kcal=2200,
        target_protein=120,
        target_fat=70,
        target_carbs=280,
    )
    plan = _post_autogenerate_plan(
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
    lunch_slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)

    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=lunch_slot["id"],
        payload={
            "recipe_id": protein_heavy_lunch["id"],
            "servings_multiplier": "2.0",
            "pinned": False,
        },
    )

    replace_response = _replace_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=lunch_slot["id"],
        payload={"avoid_current_recipe": False},
    )
    assert replace_response.status_code == 200, replace_response.text
    replaced_lunch_slot = _find_slot(replace_response.json(), day_date="2026-03-24", slot_index=0)
    assert replaced_lunch_slot["recipe_id"] == carb_friendly_lunch["id"]

    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=lunch_slot["id"],
        payload={
            "recipe_id": protein_heavy_lunch["id"],
            "servings_multiplier": "2.0",
            "pinned": False,
        },
    )

    regenerate_response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-03-24",
        payload={},
    )
    assert regenerate_response.status_code == 200, regenerate_response.text
    regenerated_lunch_slot = _find_slot(regenerate_response.json(), day_date="2026-03-24", slot_index=0)
    assert regenerated_lunch_slot["recipe_id"] == carb_friendly_lunch["id"]


def test_replace_slot_happy_path_updates_recipe_and_keeps_flags(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="replace_happy@example.com",
        username="replace_happy",
    )

    breakfast_food = create_food_via_api(
        client,
        token,
        name="Replace Happy Breakfast Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Replace Happy Dinner Food",
        kcal="200.00",
        protein="20.00",
        fat="8.00",
        carbs="16.00",
    )
    breakfast_a = _create_recipe_with_ingredient(
        client, token, name="Replace Happy Breakfast A", meal_types=["lunch"], food_id=breakfast_food["id"]
    )
    breakfast_b = _create_recipe_with_ingredient(
        client, token, name="Replace Happy Breakfast B", meal_types=["lunch"], food_id=breakfast_food["id"]
    )
    _create_recipe_with_ingredient(
        client, token, name="Replace Happy Dinner", meal_types=["dinner"], food_id=dinner_food["id"]
    )

    plan = _post_autogenerate_plan(
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
    breakfast_slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)
    assert breakfast_slot["recipe_id"] == breakfast_a["id"]

    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=breakfast_slot["id"],
        payload={"servings_multiplier": "2.5", "pinned": True},
    )

    replace_response = _replace_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=breakfast_slot["id"],
        payload={},
    )
    assert replace_response.status_code == 200, replace_response.text
    replaced_plan = replace_response.json()
    replaced_slot = _find_slot(replaced_plan, day_date="2026-03-24", slot_index=0)
    assert replaced_slot["recipe_id"] == breakfast_b["id"]
    assert Decimal(str(replaced_slot["servings_multiplier"])) > Decimal("0")
    assert replaced_slot["pinned"] is True

    shopping_response = client.get(
        f"/plans/{plan['id']}/shopping-list",
        headers=auth_headers(token),
    )
    assert shopping_response.status_code == 200, shopping_response.text

    get_plan_response = client.get(
        f"/plans/{plan['id']}",
        headers=auth_headers(token),
    )
    assert get_plan_response.status_code == 200, get_plan_response.text
    totals = get_plan_response.json()["days"][0]["totals"]
    assert Decimal(str(totals["kcal"])) > Decimal("0")


def test_replace_slot_respects_meal_types(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="replace_meal_types@example.com",
        username="replace_meal_types",
    )

    food = create_food_via_api(
        client,
        token,
        name="Replace Meal Types Food",
        kcal="120.00",
        protein="11.00",
        fat="6.00",
        carbs="14.00",
    )
    lunch_recipe = _create_recipe_with_ingredient(
        client, token, name="Replace Lunch", meal_types=["lunch"], food_id=food["id"]
    )
    breakfast_a = _create_recipe_with_ingredient(
        client, token, name="Replace Breakfast A", meal_types=["lunch"], food_id=food["id"]
    )
    breakfast_b = _create_recipe_with_ingredient(
        client, token, name="Replace Breakfast B", meal_types=["lunch"], food_id=food["id"]
    )
    dinner_recipe = _create_recipe_with_ingredient(
        client, token, name="Replace Dinner", meal_types=["dinner"], food_id=food["id"]
    )

    plan = _post_autogenerate_plan(
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
    breakfast_slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)

    replace_response = _replace_slot(client, token, plan_id=plan["id"], slot_id=breakfast_slot["id"], payload={})
    assert replace_response.status_code == 200, replace_response.text
    replaced_slot = _find_slot(replace_response.json(), day_date="2026-03-24", slot_index=0)
    assert replaced_slot["recipe_id"] in {lunch_recipe["id"], breakfast_a["id"], breakfast_b["id"]}
    assert replaced_slot["recipe_id"] != dinner_recipe["id"]


def test_replace_slot_respects_excluded_recipe_ids(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="replace_excluded_recipe@example.com",
        username="replace_excluded_recipe",
    )

    food = create_food_via_api(
        client,
        token,
        name="Replace Excluded Recipe Food",
        kcal="120.00",
        protein="11.00",
        fat="6.00",
        carbs="14.00",
    )
    breakfast_a = _create_recipe_with_ingredient(
        client, token, name="Replace Excluded Breakfast A", meal_types=["lunch"], food_id=food["id"]
    )
    breakfast_b = _create_recipe_with_ingredient(
        client, token, name="Replace Excluded Breakfast B", meal_types=["lunch"], food_id=food["id"]
    )
    breakfast_c = _create_recipe_with_ingredient(
        client, token, name="Replace Excluded Breakfast C", meal_types=["lunch"], food_id=food["id"]
    )
    _create_recipe_with_ingredient(
        client, token, name="Replace Excluded Dinner", meal_types=["dinner"], food_id=food["id"]
    )

    plan = _post_autogenerate_plan(
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
    breakfast_slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)
    assert breakfast_slot["recipe_id"] == breakfast_a["id"]

    replace_response = _replace_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=breakfast_slot["id"],
        payload={"excluded_recipe_ids": [breakfast_b["id"]]},
    )
    assert replace_response.status_code == 200, replace_response.text
    replaced_slot = _find_slot(replace_response.json(), day_date="2026-03-24", slot_index=0)
    assert replaced_slot["recipe_id"] == breakfast_c["id"]


def test_replace_slot_accepts_empty_request_body(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="replace_empty_body@example.com",
        username="replace_empty_body",
    )

    food = create_food_via_api(
        client,
        token,
        name="Replace Empty Body Food",
        kcal="120.00",
        protein="11.00",
        fat="6.00",
        carbs="14.00",
    )
    recipe_a = _create_recipe_with_ingredient(
        client, token, name="Replace Empty Body Lunch A", meal_types=["lunch"], food_id=food["id"]
    )
    _create_recipe_with_ingredient(
        client, token, name="Replace Empty Body Lunch B", meal_types=["lunch"], food_id=food["id"]
    )
    _create_recipe_with_ingredient(
        client, token, name="Replace Empty Body Dinner", meal_types=["dinner"], food_id=food["id"]
    )

    plan = _post_autogenerate_plan(
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
    breakfast_slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)
    assert breakfast_slot["recipe_id"] == recipe_a["id"]

    replace_response = _replace_slot(client, token, plan_id=plan["id"], slot_id=breakfast_slot["id"], payload=None)
    assert replace_response.status_code == 200, replace_response.text
    replaced_slot = _find_slot(replace_response.json(), day_date="2026-03-24", slot_index=0)
    assert replaced_slot["recipe_id"] != recipe_a["id"]


def test_replace_slot_repeated_with_excluded_ids_avoids_previous_variants(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="replace_history_cycle@example.com",
        username="replace_history_cycle",
    )

    food = create_food_via_api(
        client,
        token,
        name="Replace History Cycle Food",
        kcal="120.00",
        protein="11.00",
        fat="6.00",
        carbs="14.00",
    )
    recipe_a = _create_recipe_with_ingredient(
        client, token, name="Replace History Lunch A", meal_types=["lunch"], food_id=food["id"]
    )
    recipe_b = _create_recipe_with_ingredient(
        client, token, name="Replace History Lunch B", meal_types=["lunch"], food_id=food["id"]
    )
    recipe_c = _create_recipe_with_ingredient(
        client, token, name="Replace History Lunch C", meal_types=["lunch"], food_id=food["id"]
    )
    _create_recipe_with_ingredient(
        client, token, name="Replace History Dinner", meal_types=["dinner"], food_id=food["id"]
    )

    plan = _post_autogenerate_plan(
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
    breakfast_slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)
    assert breakfast_slot["recipe_id"] == recipe_a["id"]

    first_replace_response = _replace_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=breakfast_slot["id"],
        payload={},
    )
    assert first_replace_response.status_code == 200, first_replace_response.text
    first_replaced_slot = _find_slot(first_replace_response.json(), day_date="2026-03-24", slot_index=0)
    assert first_replaced_slot["recipe_id"] == recipe_b["id"]

    second_replace_response = _replace_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=breakfast_slot["id"],
        payload={"excluded_recipe_ids": [recipe_a["id"], recipe_b["id"]]},
    )
    assert second_replace_response.status_code == 200, second_replace_response.text
    second_replaced_slot = _find_slot(second_replace_response.json(), day_date="2026-03-24", slot_index=0)
    assert second_replaced_slot["recipe_id"] == recipe_c["id"]
    assert second_replaced_slot["recipe_id"] not in {recipe_a["id"], recipe_b["id"]}


def test_replace_slot_returns_friendly_422_when_all_alternatives_excluded(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="replace_friendly_422@example.com",
        username="replace_friendly_422",
    )

    food = create_food_via_api(
        client,
        token,
        name="Replace Friendly Error Food",
        kcal="120.00",
        protein="11.00",
        fat="6.00",
        carbs="14.00",
    )
    recipe_a = _create_recipe_with_ingredient(
        client, token, name="Replace Friendly Lunch A", meal_types=["lunch"], food_id=food["id"]
    )
    recipe_b = _create_recipe_with_ingredient(
        client, token, name="Replace Friendly Lunch B", meal_types=["lunch"], food_id=food["id"]
    )
    _create_recipe_with_ingredient(
        client, token, name="Replace Friendly Dinner", meal_types=["dinner"], food_id=food["id"]
    )

    plan = _post_autogenerate_plan(
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
    breakfast_slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)
    assert breakfast_slot["recipe_id"] == recipe_a["id"]

    replace_response = _replace_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=breakfast_slot["id"],
        payload={"excluded_recipe_ids": [recipe_b["id"]]},
    )
    assert replace_response.status_code == 422, replace_response.text
    assert replace_response.json()["detail"] == "Не удалось найти другую подходящую замену для этого слота."


def test_replace_slot_penalizes_near_duplicate_recipe_names_when_other_option_exists(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="replace_similarity_penalty@example.com",
        username="replace_similarity_penalty",
    )

    food = create_food_via_api(
        client,
        token,
        name="Replace Similarity Food",
        kcal="120.00",
        protein="11.00",
        fat="6.00",
        carbs="14.00",
    )
    current_recipe = _create_recipe_with_ingredient(
        client, token, name="Рис Лосось Боул", meal_types=["lunch"], food_id=food["id"]
    )
    near_duplicate_recipe = _create_recipe_with_ingredient(
        client, token, name="Лосось Рис Боул", meal_types=["lunch"], food_id=food["id"]
    )
    distinct_recipe = _create_recipe_with_ingredient(
        client, token, name="Курица Овощной Боул", meal_types=["lunch"], food_id=food["id"]
    )
    _create_recipe_with_ingredient(
        client, token, name="Replace Similarity Dinner", meal_types=["dinner"], food_id=food["id"]
    )

    plan = _post_autogenerate_plan(
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
    breakfast_slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)
    assert breakfast_slot["recipe_id"] == current_recipe["id"]

    replace_response = _replace_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=breakfast_slot["id"],
        payload={},
    )
    assert replace_response.status_code == 200, replace_response.text
    replaced_slot = _find_slot(replace_response.json(), day_date="2026-03-24", slot_index=0)
    assert replaced_slot["recipe_id"] == distinct_recipe["id"]
    assert replaced_slot["recipe_id"] != near_duplicate_recipe["id"]


def test_replace_slot_respects_excluded_food_ids(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="replace_excluded_food@example.com",
        username="replace_excluded_food",
    )

    allowed_food = create_food_via_api(
        client,
        token,
        name="Replace Allowed Ingredient Food",
        kcal="120.00",
        protein="11.00",
        fat="6.00",
        carbs="14.00",
    )
    excluded_food = create_food_via_api(
        client,
        token,
        name="Replace Excluded Ingredient Food",
        kcal="90.00",
        protein="8.00",
        fat="4.00",
        carbs="10.00",
    )
    breakfast_current = _create_recipe_with_ingredient(
        client, token, name="Replace Food Current", meal_types=["lunch"], food_id=allowed_food["id"]
    )
    breakfast_bad = _create_recipe_with_ingredient(
        client, token, name="Replace Food Bad", meal_types=["lunch"], food_id=excluded_food["id"]
    )
    breakfast_good = _create_recipe_with_ingredient(
        client, token, name="Replace Food Good", meal_types=["lunch"], food_id=allowed_food["id"]
    )
    _create_recipe_with_ingredient(
        client, token, name="Replace Food Dinner", meal_types=["dinner"], food_id=allowed_food["id"]
    )

    plan = _post_autogenerate_plan(
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
    breakfast_slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)
    assert breakfast_slot["recipe_id"] == breakfast_current["id"]

    replace_response = _replace_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=breakfast_slot["id"],
        payload={"excluded_food_ids": [excluded_food["id"]]},
    )
    assert replace_response.status_code == 200, replace_response.text
    replaced_slot = _find_slot(replace_response.json(), day_date="2026-03-24", slot_index=0)
    assert replaced_slot["recipe_id"] == breakfast_good["id"]
    assert replaced_slot["recipe_id"] != breakfast_bad["id"]


def test_replace_slot_does_not_use_foreign_private_recipes(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="replace_foreign_owner@example.com",
        username="replace_foreign_owner",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="replace_foreign_other@example.com",
        username="replace_foreign_other",
    )

    owner_food = create_food_via_api(
        client,
        owner_token,
        name="Replace Foreign Owner Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    other_food = create_food_via_api(
        client,
        other_token,
        name="Replace Foreign Other Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    _create_recipe_with_ingredient(
        client, owner_token, name="Replace Foreign Breakfast A", meal_types=["lunch"], food_id=owner_food["id"]
    )
    owner_breakfast_b = _create_recipe_with_ingredient(
        client, owner_token, name="Replace Foreign Breakfast B", meal_types=["lunch"], food_id=owner_food["id"]
    )
    _create_recipe_with_ingredient(
        client, owner_token, name="Replace Foreign Dinner", meal_types=["dinner"], food_id=owner_food["id"]
    )
    _create_recipe_with_ingredient(
        client, other_token, name="Replace Foreign Private Breakfast", meal_types=["lunch"], food_id=other_food["id"]
    )

    plan = _post_autogenerate_plan(
        client,
        owner_token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    breakfast_slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)
    replace_response = _replace_slot(
        client,
        owner_token,
        plan_id=plan["id"],
        slot_id=breakfast_slot["id"],
        payload={"excluded_recipe_ids": [owner_breakfast_b["id"]]},
    )
    assert replace_response.status_code == 422, replace_response.text


def test_replace_slot_public_visibility_rules(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="replace_visibility_owner@example.com",
        username="replace_visibility_owner",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="replace_visibility_other@example.com",
        username="replace_visibility_other",
    )

    owner_food = create_food_via_api(
        client,
        owner_token,
        name="Replace Visibility Owner Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    other_food = create_food_via_api(
        client,
        other_token,
        name="Replace Visibility Other Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    _create_recipe_with_ingredient(
        client, owner_token, name="Replace Visibility Breakfast", meal_types=["lunch"], food_id=owner_food["id"]
    )
    _create_recipe_with_ingredient(
        client, owner_token, name="Replace Visibility Dinner", meal_types=["dinner"], food_id=owner_food["id"]
    )
    public_breakfast = _create_recipe_with_ingredient(
        client, other_token, name="Replace Visibility Public Breakfast", meal_types=["lunch"], food_id=other_food["id"]
    )
    publish_recipe_via_api(client, other_token, public_breakfast["id"])

    plan = _post_autogenerate_plan(
        client,
        owner_token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    breakfast_slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)

    private_only_response = _replace_slot(
        client,
        owner_token,
        plan_id=plan["id"],
        slot_id=breakfast_slot["id"],
        payload={"use_public_recipes": False},
    )
    assert private_only_response.status_code == 422, private_only_response.text

    public_enabled_response = _replace_slot(
        client,
        owner_token,
        plan_id=plan["id"],
        slot_id=breakfast_slot["id"],
        payload={"use_public_recipes": True},
    )
    assert public_enabled_response.status_code == 200, public_enabled_response.text
    replaced_slot = _find_slot(public_enabled_response.json(), day_date="2026-03-24", slot_index=0)
    assert replaced_slot["recipe_id"] == public_breakfast["id"]


def test_replace_slot_on_other_user_plan_returns_404(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="replace_404_owner@example.com",
        username="replace_404_owner",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="replace_404_other@example.com",
        username="replace_404_other",
    )

    food = create_food_via_api(
        client,
        owner_token,
        name="Replace 404 Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    _create_recipe_with_ingredient(
        client, owner_token, name="Replace 404 Breakfast", meal_types=["lunch"], food_id=food["id"]
    )
    _create_recipe_with_ingredient(
        client, owner_token, name="Replace 404 Breakfast Alt", meal_types=["lunch"], food_id=food["id"]
    )
    _create_recipe_with_ingredient(
        client, owner_token, name="Replace 404 Dinner", meal_types=["dinner"], food_id=food["id"]
    )

    plan = _post_autogenerate_plan(
        client,
        owner_token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)
    response = _replace_slot(client, other_token, plan_id=plan["id"], slot_id=slot["id"], payload={})
    assert response.status_code == 404, response.text


def test_replace_slot_returns_422_when_only_current_recipe_matches_and_avoid_current_true(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="replace_only_current@example.com",
        username="replace_only_current",
    )

    food = create_food_via_api(
        client,
        token,
        name="Replace Only Current Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    _create_recipe_with_ingredient(
        client, token, name="Replace Only Current Breakfast", meal_types=["lunch"], food_id=food["id"]
    )
    _create_recipe_with_ingredient(
        client, token, name="Replace Only Current Dinner", meal_types=["dinner"], food_id=food["id"]
    )

    plan = _post_autogenerate_plan(
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
    breakfast_slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)
    response = _replace_slot(client, token, plan_id=plan["id"], slot_id=breakfast_slot["id"], payload={})
    assert response.status_code == 422, response.text


def test_regenerate_day_happy_path_updates_only_requested_day(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="regen_happy@example.com",
        username="regen_happy",
    )

    food = create_food_via_api(
        client,
        token,
        name="Regen Happy Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    _create_recipe_with_ingredient(client, token, name="Regen Happy Breakfast A", meal_types=["lunch"], food_id=food["id"])
    _create_recipe_with_ingredient(client, token, name="Regen Happy Breakfast B", meal_types=["lunch"], food_id=food["id"])
    _create_recipe_with_ingredient(client, token, name="Regen Happy Dinner", meal_types=["dinner"], food_id=food["id"])

    plan = _post_autogenerate_plan(
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
    before_by_key = {(slot["day_date"], slot["slot_index"]): slot["recipe_id"] for slot in plan["slots"]}
    day_slot_before = _find_slot(plan, day_date="2026-03-25", slot_index=0)

    regenerate_response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-03-25",
        payload={"excluded_recipe_ids": [day_slot_before["recipe_id"]]},
    )
    assert regenerate_response.status_code == 200, regenerate_response.text
    regenerated_plan = regenerate_response.json()
    after_by_key = {(slot["day_date"], slot["slot_index"]): slot["recipe_id"] for slot in regenerated_plan["slots"]}

    assert after_by_key[("2026-03-24", 0)] == before_by_key[("2026-03-24", 0)]
    assert after_by_key[("2026-03-24", 1)] == before_by_key[("2026-03-24", 1)]
    assert after_by_key[("2026-03-26", 0)] == before_by_key[("2026-03-26", 0)]
    assert after_by_key[("2026-03-26", 1)] == before_by_key[("2026-03-26", 1)]
    assert after_by_key[("2026-03-25", 0)] != before_by_key[("2026-03-25", 0)]


def test_regenerate_day_keeps_pinned_slots_unchanged(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="regen_pinned@example.com",
        username="regen_pinned",
    )

    food = create_food_via_api(
        client,
        token,
        name="Regen Pinned Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    _create_recipe_with_ingredient(client, token, name="Regen Pinned Breakfast A", meal_types=["lunch"], food_id=food["id"])
    _create_recipe_with_ingredient(client, token, name="Regen Pinned Breakfast B", meal_types=["lunch"], food_id=food["id"])
    _create_recipe_with_ingredient(client, token, name="Regen Pinned Dinner A", meal_types=["dinner"], food_id=food["id"])
    _create_recipe_with_ingredient(client, token, name="Regen Pinned Dinner B", meal_types=["dinner"], food_id=food["id"])

    plan = _post_autogenerate_plan(
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
    breakfast_slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)
    breakfast_recipe_before = breakfast_slot["recipe_id"]
    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=breakfast_slot["id"],
        payload={"pinned": True},
    )

    regenerate_response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-03-24",
        payload={"excluded_recipe_ids": [breakfast_recipe_before]},
    )
    assert regenerate_response.status_code == 200, regenerate_response.text
    after_slot = _find_slot(regenerate_response.json(), day_date="2026-03-24", slot_index=0)
    assert after_slot["recipe_id"] == breakfast_recipe_before
    assert after_slot["pinned"] is True


def test_regenerate_day_can_change_non_pinned_slots(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="regen_change_non_pinned@example.com",
        username="regen_change_non_pinned",
    )

    food = create_food_via_api(
        client,
        token,
        name="Regen Change Non Pinned Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    _create_recipe_with_ingredient(client, token, name="Regen Change Breakfast A", meal_types=["lunch"], food_id=food["id"])
    _create_recipe_with_ingredient(client, token, name="Regen Change Breakfast B", meal_types=["lunch"], food_id=food["id"])
    _create_recipe_with_ingredient(client, token, name="Regen Change Dinner", meal_types=["dinner"], food_id=food["id"])

    plan = _post_autogenerate_plan(
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
    breakfast_before = _find_slot(plan, day_date="2026-03-24", slot_index=0)["recipe_id"]

    regenerate_response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-03-24",
        payload={"excluded_recipe_ids": [breakfast_before]},
    )
    assert regenerate_response.status_code == 200, regenerate_response.text
    breakfast_after = _find_slot(regenerate_response.json(), day_date="2026-03-24", slot_index=0)["recipe_id"]
    assert breakfast_after != breakfast_before


def test_regenerate_day_changes_non_pinned_slots_when_viable_alternative_exists(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="regen_viable_variation@example.com",
        username="regen_viable_variation",
    )

    breakfast_food = create_food_via_api(
        client,
        token,
        name="Regen Viable Variation Breakfast Food",
        kcal="420.00",
        protein="22.00",
        fat="12.00",
        carbs="54.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Regen Viable Variation Dinner Food",
        kcal="760.00",
        protein="34.00",
        fat="24.00",
        carbs="84.00",
    )
    breakfast_a = _create_recipe_with_ingredient(
        client,
        token,
        name="Regen Viable Variation Breakfast A",
        meal_types=["lunch"],
        food_id=breakfast_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Regen Viable Variation Breakfast B",
        meal_types=["lunch"],
        food_id=breakfast_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Regen Viable Variation Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )

    plan = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    breakfast_before = _find_slot(plan, day_date="2026-03-24", slot_index=0)["recipe_id"]
    assert breakfast_before == breakfast_a["id"]

    regenerate_response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-03-24",
        payload={},
    )
    assert regenerate_response.status_code == 200, regenerate_response.text
    breakfast_after = _find_slot(regenerate_response.json(), day_date="2026-03-24", slot_index=0)["recipe_id"]
    assert breakfast_after != breakfast_before


def test_regenerate_day_keeps_current_day_when_only_current_combination_is_viable(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="regen_only_viable_current@example.com",
        username="regen_only_viable_current",
    )

    food = create_food_via_api(
        client,
        token,
        name="Regen Only Viable Current Food",
        kcal="360.00",
        protein="20.00",
        fat="10.00",
        carbs="44.00",
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Regen Only Viable Current Lunch",
        meal_types=["lunch"],
        food_id=food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Regen Only Viable Current Dinner",
        meal_types=["dinner"],
        food_id=food["id"],
    )

    plan = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    before_signature = [
        (slot["slot_index"], slot["recipe_id"], str(slot["servings_multiplier"]))
        for slot in sorted(plan["slots"], key=lambda item: (item["slot_index"], item["id"]))
    ]

    regenerate_response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-03-24",
        payload={},
    )
    assert regenerate_response.status_code == 200, regenerate_response.text
    after_signature = [
        (slot["slot_index"], slot["recipe_id"], str(slot["servings_multiplier"]))
        for slot in sorted(regenerate_response.json()["slots"], key=lambda item: (item["slot_index"], item["id"]))
    ]
    assert after_signature == before_signature


def test_regenerate_day_does_not_make_totals_much_worse_only_for_variety(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="regen_no_worse_for_variation@example.com",
        username="regen_no_worse_for_variation",
    )

    balanced_lunch_food = create_food_via_api(
        client,
        token,
        name="Regen Variation Balanced Lunch Food",
        kcal="450.00",
        protein="26.00",
        fat="12.00",
        carbs="56.00",
    )
    heavy_lunch_food = create_food_via_api(
        client,
        token,
        name="Regen Variation Heavy Lunch Food",
        kcal="980.00",
        protein="28.00",
        fat="52.00",
        carbs="92.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Regen Variation Dinner Food",
        kcal="820.00",
        protein="34.00",
        fat="24.00",
        carbs="95.00",
    )
    balanced_lunch = _create_recipe_with_ingredient(
        client,
        token,
        name="Regen Variation Balanced Lunch",
        meal_types=["lunch"],
        food_id=balanced_lunch_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Regen Variation Heavy Lunch",
        meal_types=["lunch"],
        food_id=heavy_lunch_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Regen Variation Dinner",
        meal_types=["dinner"],
        food_id=dinner_food["id"],
    )
    profile = _create_profile_via_api(
        client,
        token,
        name="Regen variation profile",
        target_kcal=1800,
        target_protein=110,
        target_fat=60,
        target_carbs=220,
    )

    plan = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "profile_id": profile["id"],
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    lunch_before = _find_slot(plan, day_date="2026-03-24", slot_index=0)["recipe_id"]
    assert lunch_before == balanced_lunch["id"]
    before_kcal = Decimal(str(plan["days"][0]["totals"]["kcal"]))

    regenerate_response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-03-24",
        payload={},
    )
    assert regenerate_response.status_code == 200, regenerate_response.text
    regenerated = regenerate_response.json()
    lunch_after = _find_slot(regenerated, day_date="2026-03-24", slot_index=0)["recipe_id"]
    after_kcal = Decimal(str(regenerated["days"][0]["totals"]["kcal"]))

    assert lunch_after == lunch_before
    assert abs(after_kcal - Decimal("1800")) <= abs(before_kcal - Decimal("1800")) + Decimal("120")


def test_regenerate_day_all_slots_pinned_returns_plan_unchanged(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="regen_all_pinned@example.com",
        username="regen_all_pinned",
    )

    food = create_food_via_api(
        client,
        token,
        name="Regen All Pinned Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    _create_recipe_with_ingredient(client, token, name="Regen All Pinned Breakfast", meal_types=["lunch"], food_id=food["id"])
    _create_recipe_with_ingredient(client, token, name="Regen All Pinned Dinner", meal_types=["dinner"], food_id=food["id"])

    plan = _post_autogenerate_plan(
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
    before_pairs = {(slot["slot_index"], slot["recipe_id"], slot["pinned"]) for slot in plan["slots"]}
    for slot in plan["slots"]:
        _patch_plan_slot(
            client,
            token,
            plan_id=plan["id"],
            slot_id=slot["id"],
            payload={"pinned": True},
        )

    regenerate_response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-03-24",
        payload={},
    )
    assert regenerate_response.status_code == 200, regenerate_response.text
    after_pairs = {(slot["slot_index"], slot["recipe_id"], slot["pinned"]) for slot in regenerate_response.json()["slots"]}
    assert after_pairs == {(index, recipe_id, True) for index, recipe_id, _ in before_pairs}


def test_regenerate_day_returns_422_when_not_enough_candidates_and_is_atomic(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="regen_not_enough@example.com",
        username="regen_not_enough",
    )

    food = create_food_via_api(
        client,
        token,
        name="Regen Not Enough Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    _create_recipe_with_ingredient(client, token, name="Regen Not Enough Breakfast", meal_types=["lunch"], food_id=food["id"])
    _create_recipe_with_ingredient(client, token, name="Regen Not Enough Dinner", meal_types=["dinner"], food_id=food["id"])

    plan = _post_autogenerate_plan(
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
    before_by_key = {(slot["day_date"], slot["slot_index"]): slot["recipe_id"] for slot in plan["slots"]}
    breakfast_slot = _find_slot(plan, day_date="2026-03-24", slot_index=0)

    regenerate_response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-03-24",
        payload={"excluded_recipe_ids": [breakfast_slot["recipe_id"]]},
    )
    assert regenerate_response.status_code == 422, regenerate_response.text

    get_plan_response = client.get(f"/plans/{plan['id']}", headers=auth_headers(token))
    assert get_plan_response.status_code == 200, get_plan_response.text
    after_by_key = {(slot["day_date"], slot["slot_index"]): slot["recipe_id"] for slot in get_plan_response.json()["slots"]}
    assert after_by_key == before_by_key


def test_regenerate_day_respects_excluded_recipe_ids(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="regen_excluded_recipe@example.com",
        username="regen_excluded_recipe",
    )

    food = create_food_via_api(
        client,
        token,
        name="Regen Excluded Recipe Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    breakfast_a = _create_recipe_with_ingredient(
        client, token, name="Regen Excluded Breakfast A", meal_types=["lunch"], food_id=food["id"]
    )
    breakfast_b = _create_recipe_with_ingredient(
        client, token, name="Regen Excluded Breakfast B", meal_types=["lunch"], food_id=food["id"]
    )
    _create_recipe_with_ingredient(client, token, name="Regen Excluded Dinner", meal_types=["dinner"], food_id=food["id"])

    plan = _post_autogenerate_plan(
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
    regenerate_response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-03-24",
        payload={"excluded_recipe_ids": [breakfast_a["id"]]},
    )
    assert regenerate_response.status_code == 200, regenerate_response.text
    breakfast_after = _find_slot(regenerate_response.json(), day_date="2026-03-24", slot_index=0)["recipe_id"]
    assert breakfast_after == breakfast_b["id"]


def test_regenerate_day_respects_excluded_food_ids(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="regen_excluded_food@example.com",
        username="regen_excluded_food",
    )

    allowed_food = create_food_via_api(
        client,
        token,
        name="Regen Allowed Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    blocked_food = create_food_via_api(
        client,
        token,
        name="Regen Blocked Food",
        kcal="90.00",
        protein="9.00",
        fat="4.00",
        carbs="18.00",
    )
    breakfast_blocked = _create_recipe_with_ingredient(
        client, token, name="Regen Blocked Breakfast", meal_types=["lunch"], food_id=blocked_food["id"]
    )
    breakfast_allowed = _create_recipe_with_ingredient(
        client, token, name="Regen Allowed Breakfast", meal_types=["lunch"], food_id=allowed_food["id"]
    )
    _create_recipe_with_ingredient(client, token, name="Regen Allowed Dinner", meal_types=["dinner"], food_id=allowed_food["id"])

    plan = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [breakfast_allowed["id"]],
            "excluded_food_ids": [],
        },
    )
    breakfast_before = _find_slot(plan, day_date="2026-03-24", slot_index=0)["recipe_id"]
    assert breakfast_before == breakfast_blocked["id"]

    regenerate_response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-03-24",
        payload={"excluded_food_ids": [blocked_food["id"]]},
    )
    assert regenerate_response.status_code == 200, regenerate_response.text
    breakfast_after = _find_slot(regenerate_response.json(), day_date="2026-03-24", slot_index=0)["recipe_id"]
    assert breakfast_after == breakfast_allowed["id"]


def test_regenerate_day_keeps_shopping_list_compatible(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="regen_shopping_compat@example.com",
        username="regen_shopping_compat",
    )

    food = create_food_via_api(
        client,
        token,
        name="Regen Shopping Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    _create_recipe_with_ingredient(client, token, name="Regen Shopping Breakfast A", meal_types=["lunch"], food_id=food["id"])
    _create_recipe_with_ingredient(client, token, name="Regen Shopping Breakfast B", meal_types=["lunch"], food_id=food["id"])
    _create_recipe_with_ingredient(client, token, name="Regen Shopping Dinner", meal_types=["dinner"], food_id=food["id"])

    plan = _post_autogenerate_plan(
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
    regenerate_response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-03-24",
        payload={},
    )
    assert regenerate_response.status_code == 200, regenerate_response.text

    shopping_response = client.get(
        f"/plans/{plan['id']}/shopping-list",
        headers=auth_headers(token),
    )
    assert shopping_response.status_code == 200, shopping_response.text


def test_regenerate_day_for_foreign_plan_returns_404(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="regen_foreign_owner@example.com",
        username="regen_foreign_owner",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="regen_foreign_other@example.com",
        username="regen_foreign_other",
    )

    food = create_food_via_api(
        client,
        owner_token,
        name="Regen Foreign Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    _create_recipe_with_ingredient(client, owner_token, name="Regen Foreign Breakfast A", meal_types=["lunch"], food_id=food["id"])
    _create_recipe_with_ingredient(client, owner_token, name="Regen Foreign Breakfast B", meal_types=["lunch"], food_id=food["id"])
    _create_recipe_with_ingredient(client, owner_token, name="Regen Foreign Dinner", meal_types=["dinner"], food_id=food["id"])

    plan = _post_autogenerate_plan(
        client,
        owner_token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    response = _regenerate_day(
        client,
        other_token,
        plan_id=plan["id"],
        day_date="2026-03-24",
        payload={},
    )
    assert response.status_code == 404, response.text


def test_regenerate_day_uses_public_recipes_only_when_enabled(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="regen_public_owner@example.com",
        username="regen_public_owner",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="regen_public_other@example.com",
        username="regen_public_other",
    )

    owner_food = create_food_via_api(
        client,
        owner_token,
        name="Regen Public Owner Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    other_food = create_food_via_api(
        client,
        other_token,
        name="Regen Public Other Food",
        kcal="120.00",
        protein="12.00",
        fat="6.00",
        carbs="18.00",
    )

    owner_breakfast = _create_recipe_with_ingredient(
        client, owner_token, name="Regen Public Owner Breakfast", meal_types=["lunch"], food_id=owner_food["id"]
    )
    _create_recipe_with_ingredient(
        client, owner_token, name="Regen Public Owner Dinner", meal_types=["dinner"], food_id=owner_food["id"]
    )

    public_breakfast = _create_recipe_with_ingredient(
        client, other_token, name="Regen Public Shared Breakfast", meal_types=["lunch"], food_id=other_food["id"]
    )
    publish_recipe_via_api(client, other_token, public_breakfast["id"])

    plan = _post_autogenerate_plan(
        client,
        owner_token,
        {
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    private_only_response = _regenerate_day(
        client,
        owner_token,
        plan_id=plan["id"],
        day_date="2026-03-24",
        payload={"use_public_recipes": False, "excluded_recipe_ids": [owner_breakfast["id"]]},
    )
    assert private_only_response.status_code == 422, private_only_response.text

    public_enabled_response = _regenerate_day(
        client,
        owner_token,
        plan_id=plan["id"],
        day_date="2026-03-24",
        payload={"use_public_recipes": True, "excluded_recipe_ids": [owner_breakfast["id"]]},
    )
    assert public_enabled_response.status_code == 200, public_enabled_response.text
    breakfast_after = _find_slot(public_enabled_response.json(), day_date="2026-03-24", slot_index=0)["recipe_id"]
    assert breakfast_after == public_breakfast["id"]


def test_regenerate_day_out_of_plan_range_returns_422(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="regen_out_of_range@example.com",
        username="regen_out_of_range",
    )

    food = create_food_via_api(
        client,
        token,
        name="Regen Out Of Range Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    _create_recipe_with_ingredient(client, token, name="Regen Out Of Range Breakfast", meal_types=["lunch"], food_id=food["id"])
    _create_recipe_with_ingredient(client, token, name="Regen Out Of Range Dinner", meal_types=["dinner"], food_id=food["id"])

    plan = _post_autogenerate_plan(
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
    response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-03-30",
        payload={},
    )
    assert response.status_code == 422, response.text


def test_replace_slot_respects_profile_excluded_foods(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="replace_profile_excluded_foods@example.com",
        username="replace_profile_excluded_foods",
    )

    allowed_food = create_food_via_api(
        client,
        token,
        name="Replace Profile Allowed Food",
        kcal="180.00",
        protein="14.00",
        fat="7.00",
        carbs="20.00",
    )
    blocked_food = create_food_via_api(
        client,
        token,
        name="Replace Profile Blocked Food",
        kcal="180.00",
        protein="14.00",
        fat="7.00",
        carbs="20.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Replace Profile Dinner Food",
        kcal="360.00",
        protein="26.00",
        fat="12.00",
        carbs="40.00",
    )

    lunch_a = _create_recipe_with_ingredient(
        client, token, name="Replace Profile Lunch A", meal_types=["lunch"], food_id=allowed_food["id"]
    )
    blocked_lunch = _create_recipe_with_ingredient(
        client, token, name="Replace Profile Blocked Lunch", meal_types=["lunch"], food_id=blocked_food["id"]
    )
    lunch_b = _create_recipe_with_ingredient(
        client, token, name="Replace Profile Lunch B", meal_types=["lunch"], food_id=allowed_food["id"]
    )
    _create_recipe_with_ingredient(
        client, token, name="Replace Profile Dinner", meal_types=["dinner"], food_id=dinner_food["id"]
    )

    profiles_response = client.get("/profiles", headers=auth_headers(token))
    assert profiles_response.status_code == 200, profiles_response.text
    profile_id = profiles_response.json()[0]["id"]
    _patch_profile_via_api(client, token, profile_id, {"excluded_food_ids": [blocked_food["id"]]})

    plan = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-05-02",
            "days_count": 1,
            "meals_per_day": 2,
            "profile_id": profile_id,
            "use_public_recipes": False,
            "excluded_recipe_ids": [lunch_b["id"]],
            "excluded_food_ids": [],
        },
    )
    lunch_slot = _find_slot(plan, day_date="2026-05-02", slot_index=0)
    assert lunch_slot["recipe_id"] == lunch_a["id"]

    replace_response = _replace_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=lunch_slot["id"],
        payload={},
    )
    assert replace_response.status_code == 200, replace_response.text
    replaced_lunch_slot = _find_slot(replace_response.json(), day_date="2026-05-02", slot_index=0)
    assert replaced_lunch_slot["recipe_id"] == lunch_b["id"]
    assert replaced_lunch_slot["recipe_id"] != blocked_lunch["id"]


def test_regenerate_day_respects_profile_excluded_foods(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="regenerate_profile_excluded_foods@example.com",
        username="regenerate_profile_excluded_foods",
    )

    allowed_food = create_food_via_api(
        client,
        token,
        name="Regenerate Profile Allowed Food",
        kcal="170.00",
        protein="13.00",
        fat="6.00",
        carbs="19.00",
    )
    blocked_food = create_food_via_api(
        client,
        token,
        name="Regenerate Profile Blocked Food",
        kcal="170.00",
        protein="13.00",
        fat="6.00",
        carbs="19.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Regenerate Profile Dinner Food",
        kcal="330.00",
        protein="24.00",
        fat="10.00",
        carbs="38.00",
    )

    lunch_a = _create_recipe_with_ingredient(
        client, token, name="Regenerate Profile Lunch A", meal_types=["lunch"], food_id=allowed_food["id"]
    )
    blocked_lunch = _create_recipe_with_ingredient(
        client, token, name="Regenerate Profile Blocked Lunch", meal_types=["lunch"], food_id=blocked_food["id"]
    )
    lunch_b = _create_recipe_with_ingredient(
        client, token, name="Regenerate Profile Lunch B", meal_types=["lunch"], food_id=allowed_food["id"]
    )
    _create_recipe_with_ingredient(
        client, token, name="Regenerate Profile Dinner", meal_types=["dinner"], food_id=dinner_food["id"]
    )

    profiles_response = client.get("/profiles", headers=auth_headers(token))
    assert profiles_response.status_code == 200, profiles_response.text
    profile_id = profiles_response.json()[0]["id"]
    _patch_profile_via_api(client, token, profile_id, {"excluded_food_ids": [blocked_food["id"]]})

    plan = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-05-03",
            "days_count": 1,
            "meals_per_day": 2,
            "profile_id": profile_id,
            "use_public_recipes": False,
            "excluded_recipe_ids": [lunch_b["id"]],
            "excluded_food_ids": [],
        },
    )
    lunch_before = _find_slot(plan, day_date="2026-05-03", slot_index=0)["recipe_id"]
    assert lunch_before == lunch_a["id"]

    regenerate_response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-05-03",
        payload={"excluded_recipe_ids": [lunch_a["id"]]},
    )
    assert regenerate_response.status_code == 200, regenerate_response.text
    lunch_after = _find_slot(regenerate_response.json(), day_date="2026-05-03", slot_index=0)["recipe_id"]
    assert lunch_after == lunch_b["id"]
    assert lunch_after != blocked_lunch["id"]


def test_replace_and_regenerate_respect_max_cook_time_override(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="replace_regen_max_cook_override@example.com",
        username="replace_regen_max_cook_override",
    )

    lunch_food = create_food_via_api(
        client,
        token,
        name="Replace Regen Max Cook Lunch Food",
        kcal="200.00",
        protein="16.00",
        fat="8.00",
        carbs="24.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Replace Regen Max Cook Dinner Food",
        kcal="360.00",
        protein="26.00",
        fat="12.00",
        carbs="40.00",
    )

    fast_a_response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json={"name": "Replace Regen Fast Lunch A", "servings_count": 1, "meal_types": ["lunch"], "cook_time_minutes": 20},
    )
    assert fast_a_response.status_code == 201, fast_a_response.text
    fast_a = fast_a_response.json()
    add_ingredient_via_api(client, token, recipe_id=fast_a["id"], food_id=lunch_food["id"], grams="100")

    slow_response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json={"name": "Replace Regen Slow Lunch", "servings_count": 1, "meal_types": ["lunch"], "cook_time_minutes": 60},
    )
    assert slow_response.status_code == 201, slow_response.text
    slow_lunch = slow_response.json()
    add_ingredient_via_api(client, token, recipe_id=slow_lunch["id"], food_id=lunch_food["id"], grams="100")

    fast_b_response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json={"name": "Replace Regen Fast Lunch B", "servings_count": 1, "meal_types": ["lunch"], "cook_time_minutes": 25},
    )
    assert fast_b_response.status_code == 201, fast_b_response.text
    fast_b = fast_b_response.json()
    add_ingredient_via_api(client, token, recipe_id=fast_b["id"], food_id=lunch_food["id"], grams="100")

    _create_recipe_with_ingredient(client, token, name="Replace Regen Max Cook Dinner", meal_types=["dinner"], food_id=dinner_food["id"])

    plan = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-05-04",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [fast_b["id"]],
            "excluded_food_ids": [],
        },
    )
    lunch_slot = _find_slot(plan, day_date="2026-05-04", slot_index=0)
    assert lunch_slot["recipe_id"] == fast_a["id"]

    replace_response = _replace_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=lunch_slot["id"],
        payload={"max_cook_time_minutes": 30},
    )
    assert replace_response.status_code == 200, replace_response.text
    replaced_lunch = _find_slot(replace_response.json(), day_date="2026-05-04", slot_index=0)
    assert replaced_lunch["recipe_id"] == fast_b["id"]
    assert replaced_lunch["recipe_id"] != slow_lunch["id"]

    regen_plan = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-05-05",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [fast_b["id"]],
            "excluded_food_ids": [],
        },
    )
    regen_response = _regenerate_day(
        client,
        token,
        plan_id=regen_plan["id"],
        day_date="2026-05-05",
        payload={"excluded_recipe_ids": [fast_a["id"]], "max_cook_time_minutes": 30},
    )
    assert regen_response.status_code == 200, regen_response.text
    regenerated_lunch = _find_slot(regen_response.json(), day_date="2026-05-05", slot_index=0)
    assert regenerated_lunch["recipe_id"] == fast_b["id"]
    assert regenerated_lunch["recipe_id"] != slow_lunch["id"]


def test_regenerate_day_returns_friendly_422_when_restrictions_filter_all_candidates(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="regenerate_friendly_422_restrictions@example.com",
        username="regenerate_friendly_422_restrictions",
    )

    lunch_food = create_food_via_api(
        client,
        token,
        name="Regenerate Friendly 422 Lunch Food",
        kcal="220.00",
        protein="17.00",
        fat="8.00",
        carbs="25.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Regenerate Friendly 422 Dinner Food",
        kcal="360.00",
        protein="25.00",
        fat="12.00",
        carbs="39.00",
    )

    lunch_response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json={"name": "Regenerate Friendly 422 Slow Lunch", "servings_count": 1, "meal_types": ["lunch"], "cook_time_minutes": 80},
    )
    assert lunch_response.status_code == 201, lunch_response.text
    slow_lunch = lunch_response.json()
    add_ingredient_via_api(client, token, recipe_id=slow_lunch["id"], food_id=lunch_food["id"], grams="100")
    _create_recipe_with_ingredient(client, token, name="Regenerate Friendly 422 Dinner", meal_types=["dinner"], food_id=dinner_food["id"])

    plan = _post_autogenerate_plan(
        client,
        token,
        {
            "start_date": "2026-05-06",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": False,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    response = _regenerate_day(
        client,
        token,
        plan_id=plan["id"],
        day_date="2026-05-06",
        payload={"max_cook_time_minutes": 30},
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "Не удалось подобрать блюда для выбранного дня с текущими ограничениями."
