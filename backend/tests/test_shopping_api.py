from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from test_plans_api import (
    add_ingredient_via_api,
    auth_headers,
    create_food_via_api,
    create_plan_via_api,
    create_recipe_via_api,
    create_user_with_token,
    publish_recipe_via_api,
    withdraw_recipe_via_api,
)


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


def _get_shopping_list(client: TestClient, token: str, *, plan_id: int) -> dict:
    response = client.get(
        f"/plans/{plan_id}/shopping-list",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_get_shopping_list_aggregates_ingredients_and_multiplier(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_agg@example.com",
        username="shopping_agg",
    )

    food_a = create_food_via_api(
        client,
        token,
        name="Shopping Food A",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    food_b = create_food_via_api(
        client,
        token,
        name="Shopping Food B",
        kcal="50.00",
        protein="5.00",
        fat="2.00",
        carbs="8.00",
    )

    recipe_a = create_recipe_via_api(client, token, name="Shopping Recipe A", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe_a["id"], food_id=food_a["id"], grams="100")
    add_ingredient_via_api(client, token, recipe_id=recipe_a["id"], food_id=food_b["id"], grams="40")

    recipe_b = create_recipe_via_api(client, token, name="Shopping Recipe B", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe_b["id"], food_id=food_a["id"], grams="30")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    slot_a = plan["slots"][0]["id"]
    slot_b = plan["slots"][1]["id"]

    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=slot_a,
        payload={"recipe_id": recipe_a["id"], "servings_multiplier": "2"},
    )
    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=slot_b,
        payload={"recipe_id": recipe_b["id"], "servings_multiplier": "1.5"},
    )

    payload = _get_shopping_list(client, token, plan_id=plan["id"])
    computed_items = [item for item in payload["items"] if item["is_manual"] is False]
    assert len(computed_items) == 2

    by_food = {item["food_id"]: item for item in computed_items}
    first = by_food[food_a["id"]]
    assert first["name"] == "Shopping Food A"
    assert Decimal(str(first["total_grams"])) == Decimal("245.00")
    assert Decimal(str(first["effective_grams"])) == Decimal("245.00")
    assert first["adjusted_grams"] is None
    assert first["checked"] is False
    assert first["excluded"] is False

    second = by_food[food_b["id"]]
    assert second["name"] == "Shopping Food B"
    assert Decimal(str(second["total_grams"])) == Decimal("80.00")
    assert Decimal(str(second["effective_grams"])) == Decimal("80.00")
    assert second["adjusted_grams"] is None
    assert second["checked"] is False
    assert second["excluded"] is False


def test_get_shopping_list_handles_empty_and_null_recipe_slots(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_empty@example.com",
        username="shopping_empty",
    )

    food = create_food_via_api(
        client,
        token,
        name="Shopping Empty Food",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    recipe = create_recipe_via_api(client, token, name="Shopping Empty Recipe", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food["id"], grams="100")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]

    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=slot_id,
        payload={"recipe_id": recipe["id"]},
    )
    with_recipe = _get_shopping_list(client, token, plan_id=plan["id"])
    computed_with_recipe = [item for item in with_recipe["items"] if item["is_manual"] is False]
    assert len(computed_with_recipe) == 1

    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=slot_id,
        payload={"recipe_id": None},
    )
    without_recipe = _get_shopping_list(client, token, plan_id=plan["id"])
    computed_without_recipe = [item for item in without_recipe["items"] if item["is_manual"] is False]
    assert computed_without_recipe == []


def test_get_shopping_list_empty_plan_returns_empty_items(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_empty_plan@example.com",
        username="shopping_empty_plan",
    )

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    payload = _get_shopping_list(client, token, plan_id=plan["id"])
    assert payload == {"items": []}


def test_shopping_endpoints_owner_only(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="shopping_owner@example.com",
        username="shopping_owner",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="shopping_other@example.com",
        username="shopping_other",
    )

    food = create_food_via_api(
        client,
        owner_token,
        name="Shopping Owner Food",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    recipe = create_recipe_via_api(client, owner_token, name="Shopping Owner Recipe", servings_count=1)
    add_ingredient_via_api(client, owner_token, recipe_id=recipe["id"], food_id=food["id"], grams="100")

    plan = create_plan_via_api(client, owner_token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]
    _patch_plan_slot(
        client,
        owner_token,
        plan_id=plan["id"],
        slot_id=slot_id,
        payload={"recipe_id": recipe["id"]},
    )

    manual_create = client.post(
        f"/plans/{plan['id']}/shopping-list/manual",
        headers=auth_headers(owner_token),
        json={"name": "Owner Manual Item", "grams": "50"},
    )
    assert manual_create.status_code == 201, manual_create.text
    manual_id = manual_create.json()["id"]

    get_foreign = client.get(f"/plans/{plan['id']}/shopping-list", headers=auth_headers(other_token))
    assert get_foreign.status_code == 404, get_foreign.text

    patch_foreign = client.patch(
        f"/plans/{plan['id']}/shopping-list/{food['id']}",
        headers=auth_headers(other_token),
        json={"checked": True},
    )
    assert patch_foreign.status_code == 404, patch_foreign.text

    post_foreign = client.post(
        f"/plans/{plan['id']}/shopping-list/manual",
        headers=auth_headers(other_token),
        json={"name": "Foreign Manual"},
    )
    assert post_foreign.status_code == 404, post_foreign.text

    delete_foreign = client.delete(
        f"/plans/{plan['id']}/shopping-list/manual/{manual_id}",
        headers=auth_headers(other_token),
    )
    assert delete_foreign.status_code == 404, delete_foreign.text


def test_patch_shopping_override_checked_and_adjusted_grams(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_override@example.com",
        username="shopping_override",
    )

    food = create_food_via_api(
        client,
        token,
        name="Shopping Override Food",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    recipe = create_recipe_via_api(client, token, name="Shopping Override Recipe", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food["id"], grams="100")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]
    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=slot_id,
        payload={"recipe_id": recipe["id"]},
    )

    set_checked = client.patch(
        f"/plans/{plan['id']}/shopping-list/{food['id']}",
        headers=auth_headers(token),
        json={"checked": True},
    )
    assert set_checked.status_code == 200, set_checked.text
    assert set_checked.json()["checked"] is True
    assert set_checked.json()["excluded"] is False

    set_adjusted = client.patch(
        f"/plans/{plan['id']}/shopping-list/{food['id']}",
        headers=auth_headers(token),
        json={"adjusted_grams": "333.33"},
    )
    assert set_adjusted.status_code == 200, set_adjusted.text
    assert Decimal(str(set_adjusted.json()["adjusted_grams"])) == Decimal("333.33")
    assert Decimal(str(set_adjusted.json()["effective_grams"])) == Decimal("333.33")

    listed = _get_shopping_list(client, token, plan_id=plan["id"])
    item = next(value for value in listed["items"] if value.get("food_id") == food["id"])
    assert item["checked"] is True
    assert item["excluded"] is False
    assert Decimal(str(item["adjusted_grams"])) == Decimal("333.33")
    assert Decimal(str(item["effective_grams"])) == Decimal("333.33")

    reset_adjusted = client.patch(
        f"/plans/{plan['id']}/shopping-list/{food['id']}",
        headers=auth_headers(token),
        json={"adjusted_grams": None},
    )
    assert reset_adjusted.status_code == 200, reset_adjusted.text
    assert reset_adjusted.json()["adjusted_grams"] is None
    assert reset_adjusted.json()["excluded"] is False
    assert Decimal(str(reset_adjusted.json()["effective_grams"])) == Decimal("100.00")

    unset_checked = client.patch(
        f"/plans/{plan['id']}/shopping-list/{food['id']}",
        headers=auth_headers(token),
        json={"checked": False},
    )
    assert unset_checked.status_code == 200, unset_checked.text
    assert unset_checked.json()["checked"] is False
    assert unset_checked.json()["excluded"] is False


def test_patch_shopping_override_excluded_hides_and_restores_computed_item(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_excluded@example.com",
        username="shopping_excluded",
    )

    food = create_food_via_api(
        client,
        token,
        name="Shopping Excluded Food",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    recipe = create_recipe_via_api(client, token, name="Shopping Excluded Recipe", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food["id"], grams="100")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=plan["slots"][0]["id"],
        payload={"recipe_id": recipe["id"]},
    )

    before_excluded = _get_shopping_list(client, token, plan_id=plan["id"])
    computed_before = [item for item in before_excluded["items"] if item["is_manual"] is False]
    assert len(computed_before) == 1

    set_excluded = client.patch(
        f"/plans/{plan['id']}/shopping-list/{food['id']}",
        headers=auth_headers(token),
        json={"excluded": True},
    )
    assert set_excluded.status_code == 200, set_excluded.text
    assert set_excluded.json()["excluded"] is True

    hidden = _get_shopping_list(client, token, plan_id=plan["id"])
    computed_hidden = [item for item in hidden["items"] if item["is_manual"] is False]
    assert computed_hidden == []

    manual_create = client.post(
        f"/plans/{plan['id']}/shopping-list/manual",
        headers=auth_headers(token),
        json={"name": "Manual survives", "grams": "12"},
    )
    assert manual_create.status_code == 201, manual_create.text
    manual_id = manual_create.json()["id"]

    hidden_with_manual = _get_shopping_list(client, token, plan_id=plan["id"])
    computed_hidden_with_manual = [item for item in hidden_with_manual["items"] if item["is_manual"] is False]
    manual_items = [item for item in hidden_with_manual["items"] if item["is_manual"] is True]
    assert computed_hidden_with_manual == []
    assert any(item["id"] == manual_id for item in manual_items)

    unset_excluded = client.patch(
        f"/plans/{plan['id']}/shopping-list/{food['id']}",
        headers=auth_headers(token),
        json={"excluded": False},
    )
    assert unset_excluded.status_code == 200, unset_excluded.text
    assert unset_excluded.json()["excluded"] is False

    visible_again = _get_shopping_list(client, token, plan_id=plan["id"])
    computed_visible_again = [item for item in visible_again["items"] if item["is_manual"] is False]
    assert len(computed_visible_again) == 1
    assert computed_visible_again[0]["food_id"] == food["id"]
    assert computed_visible_again[0]["excluded"] is False


def test_post_and_delete_manual_shopping_item(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_manual@example.com",
        username="shopping_manual",
    )

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)

    create_response = client.post(
        f"/plans/{plan['id']}/shopping-list/manual",
        headers=auth_headers(token),
        json={"name": "Бананы", "grams": "120.5", "unit": "g"},
    )
    assert create_response.status_code == 201, create_response.text
    manual = create_response.json()
    assert manual["is_manual"] is True
    assert manual["checked"] is False
    assert Decimal(str(manual["grams"])) == Decimal("120.5")
    assert manual["unit"] == "g"

    list_with_manual = _get_shopping_list(client, token, plan_id=plan["id"])
    assert any(item.get("is_manual") and item.get("id") == manual["id"] for item in list_with_manual["items"])

    delete_response = client.delete(
        f"/plans/{plan['id']}/shopping-list/manual/{manual['id']}",
        headers=auth_headers(token),
    )
    assert delete_response.status_code == 204, delete_response.text

    list_after_delete = _get_shopping_list(client, token, plan_id=plan["id"])
    assert all(item.get("id") != manual["id"] for item in list_after_delete["items"] if item.get("is_manual"))


def test_shopping_list_reflects_slot_changes_without_regeneration(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_reflect@example.com",
        username="shopping_reflect",
    )

    food_a = create_food_via_api(
        client,
        token,
        name="Reflect Food A",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    food_b = create_food_via_api(
        client,
        token,
        name="Reflect Food B",
        kcal="20.00",
        protein="2.00",
        fat="2.00",
        carbs="2.00",
    )
    recipe_a = create_recipe_via_api(client, token, name="Reflect Recipe A", servings_count=1)
    recipe_b = create_recipe_via_api(client, token, name="Reflect Recipe B", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe_a["id"], food_id=food_a["id"], grams="100")
    add_ingredient_via_api(client, token, recipe_id=recipe_b["id"], food_id=food_b["id"], grams="200")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]

    _patch_plan_slot(client, token, plan_id=plan["id"], slot_id=slot_id, payload={"recipe_id": recipe_a["id"]})
    list_with_a = _get_shopping_list(client, token, plan_id=plan["id"])
    ids_with_a = {item["food_id"] for item in list_with_a["items"] if item["is_manual"] is False}
    assert ids_with_a == {food_a["id"]}

    _patch_plan_slot(client, token, plan_id=plan["id"], slot_id=slot_id, payload={"recipe_id": recipe_b["id"]})
    list_with_b = _get_shopping_list(client, token, plan_id=plan["id"])
    ids_with_b = {item["food_id"] for item in list_with_b["items"] if item["is_manual"] is False}
    assert ids_with_b == {food_b["id"]}

    _patch_plan_slot(client, token, plan_id=plan["id"], slot_id=slot_id, payload={"recipe_id": None})
    list_without_recipe = _get_shopping_list(client, token, plan_id=plan["id"])
    ids_without_recipe = {item["food_id"] for item in list_without_recipe["items"] if item["is_manual"] is False}
    assert ids_without_recipe == set()


def test_shopping_list_recalculates_after_slot_multiplier_update(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_multiplier_recalc@example.com",
        username="shopping_multiplier_recalc",
    )

    food = create_food_via_api(
        client,
        token,
        name="Shopping Multiplier Food",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    recipe = create_recipe_via_api(client, token, name="Shopping Multiplier Recipe", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food["id"], grams="100")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]

    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=slot_id,
        payload={"recipe_id": recipe["id"], "servings_multiplier": "1"},
    )

    initial = _get_shopping_list(client, token, plan_id=plan["id"])
    initial_item = next(item for item in initial["items"] if item["is_manual"] is False)
    assert Decimal(str(initial_item["total_grams"])) == Decimal("100.00")

    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=slot_id,
        payload={"servings_multiplier": "2.5"},
    )

    recalculated = _get_shopping_list(client, token, plan_id=plan["id"])
    recalculated_item = next(item for item in recalculated["items"] if item["is_manual"] is False)
    assert Decimal(str(recalculated_item["total_grams"])) == Decimal("250.00")
    assert Decimal(str(recalculated_item["effective_grams"])) == Decimal("250.00")


def test_shopping_recompute_remains_stable_with_excluded_override(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_recompute_excluded@example.com",
        username="shopping_recompute_excluded",
    )

    food_a = create_food_via_api(
        client,
        token,
        name="Excluded Recompute Food A",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    food_b = create_food_via_api(
        client,
        token,
        name="Excluded Recompute Food B",
        kcal="20.00",
        protein="2.00",
        fat="2.00",
        carbs="2.00",
    )
    recipe_a = create_recipe_via_api(client, token, name="Excluded Recompute Recipe A", servings_count=1)
    recipe_b = create_recipe_via_api(client, token, name="Excluded Recompute Recipe B", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe_a["id"], food_id=food_a["id"], grams="100")
    add_ingredient_via_api(client, token, recipe_id=recipe_b["id"], food_id=food_b["id"], grams="100")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]

    _patch_plan_slot(client, token, plan_id=plan["id"], slot_id=slot_id, payload={"recipe_id": recipe_a["id"]})
    set_excluded = client.patch(
        f"/plans/{plan['id']}/shopping-list/{food_a['id']}",
        headers=auth_headers(token),
        json={"excluded": True},
    )
    assert set_excluded.status_code == 200, set_excluded.text

    hidden_a = _get_shopping_list(client, token, plan_id=plan["id"])
    ids_hidden_a = {item["food_id"] for item in hidden_a["items"] if item["is_manual"] is False}
    assert ids_hidden_a == set()

    _patch_plan_slot(client, token, plan_id=plan["id"], slot_id=slot_id, payload={"recipe_id": recipe_b["id"]})
    with_b = _get_shopping_list(client, token, plan_id=plan["id"])
    ids_with_b = {item["food_id"] for item in with_b["items"] if item["is_manual"] is False}
    assert ids_with_b == {food_b["id"]}

    _patch_plan_slot(client, token, plan_id=plan["id"], slot_id=slot_id, payload={"recipe_id": recipe_a["id"]})
    hidden_a_again = _get_shopping_list(client, token, plan_id=plan["id"])
    ids_hidden_a_again = {item["food_id"] for item in hidden_a_again["items"] if item["is_manual"] is False}
    assert ids_hidden_a_again == set()


def test_withdrawn_recipe_after_selected_does_not_break_plan_shopping_owner_only(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _plan_owner, token_owner = create_user_with_token(
        db_session_factory,
        email="shopping_withdrawn_owner@example.com",
        username="shopping_withdrawn_owner",
    )
    _recipe_owner, token_recipe_owner = create_user_with_token(
        db_session_factory,
        email="shopping_withdrawn_recipe_owner@example.com",
        username="shopping_withdrawn_recipe_owner",
    )
    _other_user, token_other = create_user_with_token(
        db_session_factory,
        email="shopping_withdrawn_other@example.com",
        username="shopping_withdrawn_other",
    )

    food = create_food_via_api(
        client,
        token_recipe_owner,
        name="Withdrawn Scenario Food",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    recipe = create_recipe_via_api(client, token_recipe_owner, name="Withdrawn Scenario Recipe", servings_count=1)
    add_ingredient_via_api(client, token_recipe_owner, recipe_id=recipe["id"], food_id=food["id"], grams="120")
    published = publish_recipe_via_api(client, token_recipe_owner, recipe["id"])

    plan = create_plan_via_api(client, token_owner, start_date="2026-03-24", days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]
    set_recipe = client.patch(
        f"/plans/{plan['id']}/slots/{slot_id}",
        headers=auth_headers(token_owner),
        json={"recipe_id": published["id"]},
    )
    assert set_recipe.status_code == 200, set_recipe.text

    withdrawn = withdraw_recipe_via_api(client, token_recipe_owner, recipe["id"])
    assert withdrawn["is_listed"] is False

    owner_plan = client.get(f"/plans/{plan['id']}", headers=auth_headers(token_owner))
    assert owner_plan.status_code == 200, owner_plan.text
    assert owner_plan.json()["days"][0]["slots"][0]["recipe_id"] == recipe["id"]

    owner_shopping = client.get(f"/plans/{plan['id']}/shopping-list", headers=auth_headers(token_owner))
    assert owner_shopping.status_code == 200, owner_shopping.text
    computed_owner = [item for item in owner_shopping.json()["items"] if item["is_manual"] is False]
    assert len(computed_owner) == 1
    assert Decimal(str(computed_owner[0]["total_grams"])) == Decimal("120.00")

    foreign_plan = client.get(f"/plans/{plan['id']}", headers=auth_headers(token_other))
    assert foreign_plan.status_code == 404, foreign_plan.text

    foreign_shopping = client.get(f"/plans/{plan['id']}/shopping-list", headers=auth_headers(token_other))
    assert foreign_shopping.status_code == 404, foreign_shopping.text


def test_shopping_list_decimal_rounding_is_stable(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_rounding@example.com",
        username="shopping_rounding",
    )

    food = create_food_via_api(
        client,
        token,
        name="Shopping Rounding Food",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    recipe = create_recipe_via_api(client, token, name="Shopping Rounding Recipe", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food["id"], grams="10.01")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]
    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=slot_id,
        payload={"recipe_id": recipe["id"], "servings_multiplier": "1.333"},
    )

    payload = _get_shopping_list(client, token, plan_id=plan["id"])
    item = next(value for value in payload["items"] if value["is_manual"] is False)
    assert Decimal(str(item["total_grams"])) == Decimal("13.34")
    assert Decimal(str(item["effective_grams"])) == Decimal("13.34")


def test_shopping_validation_for_adjusted_and_manual_grams(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_validation@example.com",
        username="shopping_validation",
    )

    food = create_food_via_api(
        client,
        token,
        name="Shopping Validation Food",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    recipe = create_recipe_via_api(client, token, name="Shopping Validation Recipe", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food["id"], grams="100")
    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=plan["slots"][0]["id"],
        payload={"recipe_id": recipe["id"]},
    )

    invalid_adjusted = client.patch(
        f"/plans/{plan['id']}/shopping-list/{food['id']}",
        headers=auth_headers(token),
        json={"adjusted_grams": "0"},
    )
    assert invalid_adjusted.status_code == 422, invalid_adjusted.text

    invalid_manual = client.post(
        f"/plans/{plan['id']}/shopping-list/manual",
        headers=auth_headers(token),
        json={"name": "Invalid manual", "grams": "0"},
    )
    assert invalid_manual.status_code == 422, invalid_manual.text
