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
    payload: dict,
):
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
        client, token, name="Replace Happy Breakfast A", meal_types=["breakfast"], food_id=breakfast_food["id"]
    )
    breakfast_b = _create_recipe_with_ingredient(
        client, token, name="Replace Happy Breakfast B", meal_types=["breakfast"], food_id=breakfast_food["id"]
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
    assert Decimal(str(replaced_slot["servings_multiplier"])) == Decimal("2.5")
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
        client, token, name="Replace Breakfast A", meal_types=["breakfast"], food_id=food["id"]
    )
    breakfast_b = _create_recipe_with_ingredient(
        client, token, name="Replace Breakfast B", meal_types=["breakfast"], food_id=food["id"]
    )
    _create_recipe_with_ingredient(
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
    assert replaced_slot["recipe_id"] in {breakfast_a["id"], breakfast_b["id"]}
    assert replaced_slot["recipe_id"] != lunch_recipe["id"]


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
        client, token, name="Replace Excluded Breakfast A", meal_types=["breakfast"], food_id=food["id"]
    )
    breakfast_b = _create_recipe_with_ingredient(
        client, token, name="Replace Excluded Breakfast B", meal_types=["breakfast"], food_id=food["id"]
    )
    breakfast_c = _create_recipe_with_ingredient(
        client, token, name="Replace Excluded Breakfast C", meal_types=["breakfast"], food_id=food["id"]
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
        client, token, name="Replace Food Current", meal_types=["breakfast"], food_id=allowed_food["id"]
    )
    breakfast_bad = _create_recipe_with_ingredient(
        client, token, name="Replace Food Bad", meal_types=["breakfast"], food_id=excluded_food["id"]
    )
    breakfast_good = _create_recipe_with_ingredient(
        client, token, name="Replace Food Good", meal_types=["breakfast"], food_id=allowed_food["id"]
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
        client, owner_token, name="Replace Foreign Breakfast A", meal_types=["breakfast"], food_id=owner_food["id"]
    )
    owner_breakfast_b = _create_recipe_with_ingredient(
        client, owner_token, name="Replace Foreign Breakfast B", meal_types=["breakfast"], food_id=owner_food["id"]
    )
    _create_recipe_with_ingredient(
        client, owner_token, name="Replace Foreign Dinner", meal_types=["dinner"], food_id=owner_food["id"]
    )
    _create_recipe_with_ingredient(
        client, other_token, name="Replace Foreign Private Breakfast", meal_types=["breakfast"], food_id=other_food["id"]
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
        client, owner_token, name="Replace Visibility Breakfast", meal_types=["breakfast"], food_id=owner_food["id"]
    )
    _create_recipe_with_ingredient(
        client, owner_token, name="Replace Visibility Dinner", meal_types=["dinner"], food_id=owner_food["id"]
    )
    public_breakfast = _create_recipe_with_ingredient(
        client, other_token, name="Replace Visibility Public Breakfast", meal_types=["breakfast"], food_id=other_food["id"]
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
        client, owner_token, name="Replace 404 Breakfast", meal_types=["breakfast"], food_id=food["id"]
    )
    _create_recipe_with_ingredient(
        client, owner_token, name="Replace 404 Breakfast Alt", meal_types=["breakfast"], food_id=food["id"]
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
        client, token, name="Replace Only Current Breakfast", meal_types=["breakfast"], food_id=food["id"]
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
    _create_recipe_with_ingredient(client, token, name="Regen Happy Breakfast A", meal_types=["breakfast"], food_id=food["id"])
    _create_recipe_with_ingredient(client, token, name="Regen Happy Breakfast B", meal_types=["breakfast"], food_id=food["id"])
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
    _create_recipe_with_ingredient(client, token, name="Regen Pinned Breakfast A", meal_types=["breakfast"], food_id=food["id"])
    _create_recipe_with_ingredient(client, token, name="Regen Pinned Breakfast B", meal_types=["breakfast"], food_id=food["id"])
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
    _create_recipe_with_ingredient(client, token, name="Regen Change Breakfast A", meal_types=["breakfast"], food_id=food["id"])
    _create_recipe_with_ingredient(client, token, name="Regen Change Breakfast B", meal_types=["breakfast"], food_id=food["id"])
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
    _create_recipe_with_ingredient(client, token, name="Regen All Pinned Breakfast", meal_types=["breakfast"], food_id=food["id"])
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
    _create_recipe_with_ingredient(client, token, name="Regen Not Enough Breakfast", meal_types=["breakfast"], food_id=food["id"])
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
        client, token, name="Regen Excluded Breakfast A", meal_types=["breakfast"], food_id=food["id"]
    )
    breakfast_b = _create_recipe_with_ingredient(
        client, token, name="Regen Excluded Breakfast B", meal_types=["breakfast"], food_id=food["id"]
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
        client, token, name="Regen Blocked Breakfast", meal_types=["breakfast"], food_id=blocked_food["id"]
    )
    breakfast_allowed = _create_recipe_with_ingredient(
        client, token, name="Regen Allowed Breakfast", meal_types=["breakfast"], food_id=allowed_food["id"]
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
    _create_recipe_with_ingredient(client, token, name="Regen Shopping Breakfast A", meal_types=["breakfast"], food_id=food["id"])
    _create_recipe_with_ingredient(client, token, name="Regen Shopping Breakfast B", meal_types=["breakfast"], food_id=food["id"])
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
    _create_recipe_with_ingredient(client, owner_token, name="Regen Foreign Breakfast A", meal_types=["breakfast"], food_id=food["id"])
    _create_recipe_with_ingredient(client, owner_token, name="Regen Foreign Breakfast B", meal_types=["breakfast"], food_id=food["id"])
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
    _create_recipe_with_ingredient(client, token, name="Regen Out Of Range Breakfast", meal_types=["breakfast"], food_id=food["id"])
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
