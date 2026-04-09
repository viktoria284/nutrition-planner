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

MEAL_SEQUENCE_BY_MEALS_PER_DAY = {
    2: ["breakfast", "dinner"],
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
        meal_types=["breakfast"],
        food_id=food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Allowed Breakfast",
        meal_types=["breakfast"],
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
        meal_types=["breakfast"],
        food_id=excluded_food["id"],
    )
    _create_recipe_with_ingredient(
        client,
        token,
        name="Breakfast Allowed Food",
        meal_types=["breakfast"],
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
    assert "meal_type=breakfast" in response.json()["detail"]
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
        meal_types=["breakfast"],
        food_id=food["id"],
    )
    breakfast_b = _create_recipe_with_ingredient(
        client,
        token,
        name="Breakfast Candidate B",
        meal_types=["breakfast"],
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
        meal_types=["breakfast"],
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
        meal_types=["breakfast"],
        food_id=other_food["id"],
    )
    other_public_breakfast = _create_recipe_with_ingredient(
        client,
        other_token,
        name="Other Breakfast Public",
        meal_types=["breakfast"],
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
