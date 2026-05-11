from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.shopping import ShoppingListItem, ShoppingListSource
from test_plans_api import (
    add_ingredient_via_api,
    auth_headers,
    create_food_via_api,
    create_plan_via_api,
    create_recipe_via_api,
    create_user_with_token,
)


def _create_food_with_category(
    client: TestClient,
    token: str,
    *,
    name: str,
    category: str,
    kcal: str = "100.00",
    protein: str = "10.00",
    fat: str = "5.00",
    carbs: str = "20.00",
) -> dict:
    response = client.post(
        "/foods",
        headers=auth_headers(token),
        json={
            "name": name,
            "kcal": kcal,
            "protein": protein,
            "fat": fat,
            "carbs": carbs,
            "category": category,
        },
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


def _create_shopping_list_from_plan(
    client: TestClient,
    token: str,
    *,
    plan_id: int,
    title: str | None = None,
) -> dict:
    payload = {"plan_id": plan_id}
    if title is not None:
        payload["title"] = title

    response = client.post(
        "/shopping-lists/from-plan",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _get_shopping_list(client: TestClient, token: str, shopping_list_id: int) -> dict:
    response = client.get(
        f"/shopping-lists/{shopping_list_id}",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _list_shopping_lists(client: TestClient, token: str) -> list[dict]:
    response = client.get("/shopping-lists", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


def _patch_item(
    client: TestClient,
    token: str,
    *,
    shopping_list_id: int,
    item_id: int,
    payload: dict,
) -> dict:
    response = client.patch(
        f"/shopping-lists/{shopping_list_id}/items/{item_id}",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _add_manual_item(
    client: TestClient,
    token: str,
    *,
    shopping_list_id: int,
    payload: dict,
) -> dict:
    response = client.post(
        f"/shopping-lists/{shopping_list_id}/items/manual",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _delete_item(
    client: TestClient,
    token: str,
    *,
    shopping_list_id: int,
    item_id: int,
) -> None:
    response = client.delete(
        f"/shopping-lists/{shopping_list_id}/items/{item_id}",
        headers=auth_headers(token),
    )
    assert response.status_code == 204, response.text


def _rebuild_list(client: TestClient, token: str, shopping_list_id: int) -> dict:
    response = client.post(
        f"/shopping-lists/{shopping_list_id}/rebuild",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _merge_lists(client: TestClient, token: str, payload: dict) -> dict:
    response = client.post("/shopping-lists/merge", headers=auth_headers(token), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _bulk_delete_lists(client: TestClient, token: str, shopping_list_ids: list[int]) -> dict:
    response = client.post(
        "/shopping-lists/bulk-delete",
        headers=auth_headers(token),
        json={"shopping_list_ids": shopping_list_ids},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_empty_shopping_list(
    client: TestClient,
    token: str,
    *,
    start_date: str,
    title: str,
) -> dict:
    plan = create_plan_via_api(client, token, start_date=start_date, days_count=1, meals_per_day=2, title=title)
    return _create_shopping_list_from_plan(client, token, plan_id=plan["id"], title=title)


def _computed_items(payload: dict) -> list[dict]:
    return [item for item in payload["items"] if item["item_type"] == "computed"]


def _manual_items(payload: dict) -> list[dict]:
    return [item for item in payload["items"] if item["item_type"] == "manual"]


def test_create_from_plan_creates_materialized_entities_and_aggregation(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_new_create@example.com",
        username="shopping_new_create",
    )

    food_a = _create_food_with_category(client, token, name="Shopping Cat A", category="vegetables")
    food_b = _create_food_with_category(client, token, name="Shopping Cat B", category="fruits")

    recipe_a = create_recipe_via_api(client, token, name="Shopping Recipe A", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe_a["id"], food_id=food_a["id"], grams="100")
    add_ingredient_via_api(client, token, recipe_id=recipe_a["id"], food_id=food_b["id"], grams="10.01")

    recipe_b = create_recipe_via_api(client, token, name="Shopping Recipe B", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe_b["id"], food_id=food_a["id"], grams="30")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=plan["slots"][0]["id"],
        payload={"recipe_id": recipe_a["id"], "servings_multiplier": "2"},
    )
    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=plan["slots"][1]["id"],
        payload={"recipe_id": recipe_b["id"], "servings_multiplier": "1.5"},
    )

    created = _create_shopping_list_from_plan(client, token, plan_id=plan["id"])
    assert created["source_type"] == "plan"
    assert created["status"] == "active"
    assert created["is_outdated"] is False
    assert len(created["sources"]) == 1
    assert created["sources"][0]["plan_id"] == plan["id"]

    computed = _computed_items(created)
    assert len(computed) == 2

    by_food = {item["food_id"]: item for item in computed}
    item_a = by_food[food_a["id"]]
    assert Decimal(str(item_a["planned_grams"])) == Decimal("245.00")
    assert Decimal(str(item_a["effective_grams"])) == Decimal("245.00")
    assert item_a["category"] == "vegetables"

    item_b = by_food[food_b["id"]]
    assert Decimal(str(item_b["planned_grams"])) == Decimal("20.02")
    assert item_b["category"] == "fruits"


def test_owner_only_shopping_list_endpoints(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="shopping_owner_new@example.com",
        username="shopping_owner_new",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="shopping_other_new@example.com",
        username="shopping_other_new",
    )

    food = create_food_via_api(
        client,
        owner_token,
        name="Owner Food",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    recipe = create_recipe_via_api(client, owner_token, name="Owner Recipe", servings_count=1)
    add_ingredient_via_api(client, owner_token, recipe_id=recipe["id"], food_id=food["id"], grams="100")

    plan = create_plan_via_api(client, owner_token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    _patch_plan_slot(
        client,
        owner_token,
        plan_id=plan["id"],
        slot_id=plan["slots"][0]["id"],
        payload={"recipe_id": recipe["id"]},
    )

    created = _create_shopping_list_from_plan(client, owner_token, plan_id=plan["id"])
    list_id = created["id"]
    item_id = _computed_items(created)[0]["id"]

    get_foreign = client.get(f"/shopping-lists/{list_id}", headers=auth_headers(other_token))
    assert get_foreign.status_code == 404, get_foreign.text

    patch_foreign = client.patch(
        f"/shopping-lists/{list_id}/items/{item_id}",
        headers=auth_headers(other_token),
        json={"checked": True},
    )
    assert patch_foreign.status_code == 404, patch_foreign.text

    add_foreign = client.post(
        f"/shopping-lists/{list_id}/items/manual",
        headers=auth_headers(other_token),
        json={"name": "Foreign Manual"},
    )
    assert add_foreign.status_code == 404, add_foreign.text

    rebuild_foreign = client.post(
        f"/shopping-lists/{list_id}/rebuild",
        headers=auth_headers(other_token),
    )
    assert rebuild_foreign.status_code == 404, rebuild_foreign.text

    create_from_foreign_plan = client.post(
        "/shopping-lists/from-plan",
        headers=auth_headers(other_token),
        json={"plan_id": plan["id"]},
    )
    assert create_from_foreign_plan.status_code == 404, create_from_foreign_plan.text


def test_create_from_empty_plan_and_list_summaries(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_empty_new@example.com",
        username="shopping_empty_new",
    )

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    created = _create_shopping_list_from_plan(client, token, plan_id=plan["id"], title="Мой список")

    assert created["title"] == "Мой список"
    assert created["items"] == []

    listed = _list_shopping_lists(client, token)
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]
    assert listed[0]["source_plan_ids"] == [plan["id"]]
    assert listed[0]["items_total"] == 0


def test_update_item_checked_and_adjusted_persists(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_update_item_new@example.com",
        username="shopping_update_item_new",
    )

    food = create_food_via_api(
        client,
        token,
        name="Update Food",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    recipe = create_recipe_via_api(client, token, name="Update Recipe", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food["id"], grams="100")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    _patch_plan_slot(client, token, plan_id=plan["id"], slot_id=plan["slots"][0]["id"], payload={"recipe_id": recipe["id"]})

    created = _create_shopping_list_from_plan(client, token, plan_id=plan["id"])
    computed_item = _computed_items(created)[0]

    patched_checked = _patch_item(
        client,
        token,
        shopping_list_id=created["id"],
        item_id=computed_item["id"],
        payload={"checked": True},
    )
    assert patched_checked["checked"] is True

    patched_adjusted = _patch_item(
        client,
        token,
        shopping_list_id=created["id"],
        item_id=computed_item["id"],
        payload={"adjusted_grams": "333.33"},
    )
    assert Decimal(str(patched_adjusted["adjusted_grams"])) == Decimal("333.33")

    loaded = _get_shopping_list(client, token, created["id"])
    loaded_item = next(item for item in loaded["items"] if item["id"] == computed_item["id"])
    assert loaded_item["checked"] is True
    assert Decimal(str(loaded_item["adjusted_grams"])) == Decimal("333.33")
    assert Decimal(str(loaded_item["effective_grams"])) == Decimal("333.33")


def test_manual_item_add_and_delete(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_manual_new@example.com",
        username="shopping_manual_new",
    )

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    created = _create_shopping_list_from_plan(client, token, plan_id=plan["id"])

    manual = _add_manual_item(
        client,
        token,
        shopping_list_id=created["id"],
        payload={"name": "Бананы", "category": "fruits", "unit": "g", "adjusted_grams": "120.5"},
    )
    assert manual["item_type"] == "manual"
    assert manual["category"] == "fruits"
    assert Decimal(str(manual["adjusted_grams"])) == Decimal("120.5")

    with_manual = _get_shopping_list(client, token, created["id"])
    assert any(item["id"] == manual["id"] for item in _manual_items(with_manual))

    _delete_item(client, token, shopping_list_id=created["id"], item_id=manual["id"])

    after_delete = _get_shopping_list(client, token, created["id"])
    assert all(item["id"] != manual["id"] for item in _manual_items(after_delete))


def test_delete_computed_item_marks_excluded(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_delete_computed_new@example.com",
        username="shopping_delete_computed_new",
    )

    food = create_food_via_api(
        client,
        token,
        name="Delete Computed Food",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    recipe = create_recipe_via_api(client, token, name="Delete Computed Recipe", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food["id"], grams="100")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    _patch_plan_slot(client, token, plan_id=plan["id"], slot_id=plan["slots"][0]["id"], payload={"recipe_id": recipe["id"]})
    created = _create_shopping_list_from_plan(client, token, plan_id=plan["id"])

    computed_item = _computed_items(created)[0]
    _delete_item(client, token, shopping_list_id=created["id"], item_id=computed_item["id"])

    loaded = _get_shopping_list(client, token, created["id"])
    excluded_item = next(item for item in loaded["items"] if item["id"] == computed_item["id"])
    assert excluded_item["item_type"] == "computed"
    assert excluded_item["excluded"] is True


def test_rebuild_updates_planned_grams_and_preserves_manual_and_overrides(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_rebuild_new@example.com",
        username="shopping_rebuild_new",
    )

    food = _create_food_with_category(client, token, name="Rebuild Food", category="grains_bakery")
    recipe = create_recipe_via_api(client, token, name="Rebuild Recipe", servings_count=1)
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

    created = _create_shopping_list_from_plan(client, token, plan_id=plan["id"])
    computed_item = _computed_items(created)[0]

    _patch_item(
        client,
        token,
        shopping_list_id=created["id"],
        item_id=computed_item["id"],
        payload={"checked": True, "adjusted_grams": "90.00"},
    )
    manual = _add_manual_item(
        client,
        token,
        shopping_list_id=created["id"],
        payload={"name": "Manual Keep", "category": "other"},
    )

    _patch_plan_slot(
        client,
        token,
        plan_id=plan["id"],
        slot_id=slot_id,
        payload={"servings_multiplier": "2.5"},
    )

    rebuilt = _rebuild_list(client, token, created["id"])
    rebuilt_computed = next(item for item in _computed_items(rebuilt) if item["food_id"] == food["id"])
    assert Decimal(str(rebuilt_computed["planned_grams"])) == Decimal("250.00")
    assert rebuilt_computed["checked"] is True
    assert Decimal(str(rebuilt_computed["adjusted_grams"])) == Decimal("90.00")
    assert rebuilt_computed["category"] == "grains_bakery"

    manual_items = _manual_items(rebuilt)
    assert any(item["id"] == manual["id"] for item in manual_items)


def test_changed_plan_marks_list_outdated_until_rebuild(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_outdated_new@example.com",
        username="shopping_outdated_new",
    )

    food = create_food_via_api(
        client,
        token,
        name="Outdated Food",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    recipe = create_recipe_via_api(client, token, name="Outdated Recipe", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food["id"], grams="100")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]
    _patch_plan_slot(client, token, plan_id=plan["id"], slot_id=slot_id, payload={"recipe_id": recipe["id"]})

    created = _create_shopping_list_from_plan(client, token, plan_id=plan["id"])
    assert created["is_outdated"] is False

    _patch_plan_slot(client, token, plan_id=plan["id"], slot_id=slot_id, payload={"servings_multiplier": "2"})

    outdated = _get_shopping_list(client, token, created["id"])
    assert outdated["is_outdated"] is True

    rebuilt = _rebuild_list(client, token, created["id"])
    assert rebuilt["is_outdated"] is False


def test_get_plan_shopping_list_compatibility_endpoint_returns_materialized_list(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_plan_compat_new@example.com",
        username="shopping_plan_compat_new",
    )

    food = create_food_via_api(
        client,
        token,
        name="Compat Food",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    recipe = create_recipe_via_api(client, token, name="Compat Recipe", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food["id"], grams="100")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    _patch_plan_slot(client, token, plan_id=plan["id"], slot_id=plan["slots"][0]["id"], payload={"recipe_id": recipe["id"]})

    first = client.get(f"/plans/{plan['id']}/shopping-list", headers=auth_headers(token))
    assert first.status_code == 200, first.text
    first_payload = first.json()
    assert "id" in first_payload
    assert len(_computed_items(first_payload)) == 1

    second = client.get(f"/plans/{plan['id']}/shopping-list", headers=auth_headers(token))
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first_payload["id"]


def test_delete_shopping_list_owner_only_and_cascades(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="shopping_delete_owner@example.com",
        username="shopping_delete_owner",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="shopping_delete_other@example.com",
        username="shopping_delete_other",
    )

    food = create_food_via_api(
        client,
        owner_token,
        name="Delete Cascade Food",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    recipe = create_recipe_via_api(client, owner_token, name="Delete Cascade Recipe", servings_count=1)
    add_ingredient_via_api(client, owner_token, recipe_id=recipe["id"], food_id=food["id"], grams="100")
    plan = create_plan_via_api(client, owner_token, start_date="2026-04-01", days_count=1, meals_per_day=2)
    _patch_plan_slot(
        client,
        owner_token,
        plan_id=plan["id"],
        slot_id=plan["slots"][0]["id"],
        payload={"recipe_id": recipe["id"]},
    )
    shopping_list = _create_shopping_list_from_plan(client, owner_token, plan_id=plan["id"])
    _add_manual_item(
        client,
        owner_token,
        shopping_list_id=shopping_list["id"],
        payload={"name": "Пакеты", "category": "other", "unit": "шт", "adjusted_grams": "2"},
    )

    other_delete = client.delete(f"/shopping-lists/{shopping_list['id']}", headers=auth_headers(other_token))
    assert other_delete.status_code == 404, other_delete.text

    owner_delete = client.delete(f"/shopping-lists/{shopping_list['id']}", headers=auth_headers(owner_token))
    assert owner_delete.status_code == 204, owner_delete.text

    after_delete = client.get(f"/shopping-lists/{shopping_list['id']}", headers=auth_headers(owner_token))
    assert after_delete.status_code == 404, after_delete.text

    with db_session_factory() as db:
        orphan_items = db.execute(
            select(ShoppingListItem).where(ShoppingListItem.shopping_list_id == shopping_list["id"])
        ).scalars().all()
        orphan_sources = db.execute(
            select(ShoppingListSource).where(ShoppingListSource.shopping_list_id == shopping_list["id"])
        ).scalars().all()
    assert orphan_items == []
    assert orphan_sources == []


def test_bulk_delete_two_own_lists_success(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_bulk_delete_owner@example.com",
        username="shopping_bulk_delete_owner",
    )

    first = _create_empty_shopping_list(client, token, start_date="2026-04-06", title="Первый bulk список")
    second = _create_empty_shopping_list(client, token, start_date="2026-04-07", title="Второй bulk список")
    keep = _create_empty_shopping_list(client, token, start_date="2026-04-08", title="Оставить список")

    result = _bulk_delete_lists(client, token, [first["id"], second["id"]])
    assert result == {"deleted_count": 2}

    for shopping_list in (first, second):
        response = client.get(f"/shopping-lists/{shopping_list['id']}", headers=auth_headers(token))
        assert response.status_code == 404, response.text

    kept = _get_shopping_list(client, token, keep["id"])
    assert kept["id"] == keep["id"]


def test_bulk_delete_empty_ids_returns_422(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_bulk_delete_empty@example.com",
        username="shopping_bulk_delete_empty",
    )

    response = client.post(
        "/shopping-lists/bulk-delete",
        headers=auth_headers(token),
        json={"shopping_list_ids": []},
    )
    assert response.status_code == 422, response.text


def test_bulk_delete_duplicate_ids_are_deduplicated(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_bulk_delete_duplicate@example.com",
        username="shopping_bulk_delete_duplicate",
    )

    shopping_list = _create_empty_shopping_list(
        client,
        token,
        start_date="2026-04-09",
        title="Дублированный список",
    )

    result = _bulk_delete_lists(client, token, [shopping_list["id"], shopping_list["id"]])
    assert result == {"deleted_count": 1}

    response = client.get(f"/shopping-lists/{shopping_list['id']}", headers=auth_headers(token))
    assert response.status_code == 404, response.text


def test_bulk_delete_foreign_id_returns_404_without_partial_delete(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="shopping_bulk_delete_owner_only@example.com",
        username="shopping_bulk_delete_owner_only",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="shopping_bulk_delete_foreign@example.com",
        username="shopping_bulk_delete_foreign",
    )

    owner_list = _create_empty_shopping_list(
        client,
        owner_token,
        start_date="2026-04-10",
        title="Мой список",
    )
    foreign_list = _create_empty_shopping_list(
        client,
        other_token,
        start_date="2026-04-11",
        title="Чужой список",
    )

    response = client.post(
        "/shopping-lists/bulk-delete",
        headers=auth_headers(owner_token),
        json={"shopping_list_ids": [owner_list["id"], foreign_list["id"]]},
    )
    assert response.status_code == 404, response.text

    still_exists = _get_shopping_list(client, owner_token, owner_list["id"])
    assert still_exists["id"] == owner_list["id"]


def test_merge_requires_at_least_two_lists(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_merge_min@example.com",
        username="shopping_merge_min",
    )

    response = client.post(
        "/shopping-lists/merge",
        headers=auth_headers(token),
        json={"shopping_list_ids": [1], "title": "Недостаточно списков"},
    )
    assert response.status_code == 422, response.text


def test_merge_owner_only_returns_404(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="shopping_merge_owner@example.com",
        username="shopping_merge_owner",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="shopping_merge_other@example.com",
        username="shopping_merge_other",
    )

    owner_food = create_food_via_api(
        client,
        owner_token,
        name="Owner Merge Food",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    owner_recipe = create_recipe_via_api(client, owner_token, name="Owner Merge Recipe", servings_count=1)
    add_ingredient_via_api(client, owner_token, recipe_id=owner_recipe["id"], food_id=owner_food["id"], grams="100")
    owner_plan = create_plan_via_api(client, owner_token, start_date="2026-04-02", days_count=1, meals_per_day=2)
    _patch_plan_slot(
        client,
        owner_token,
        plan_id=owner_plan["id"],
        slot_id=owner_plan["slots"][0]["id"],
        payload={"recipe_id": owner_recipe["id"]},
    )
    owner_list = _create_shopping_list_from_plan(client, owner_token, plan_id=owner_plan["id"])

    other_food = create_food_via_api(
        client,
        other_token,
        name="Other Merge Food",
        kcal="10.00",
        protein="1.00",
        fat="1.00",
        carbs="1.00",
    )
    other_recipe = create_recipe_via_api(client, other_token, name="Other Merge Recipe", servings_count=1)
    add_ingredient_via_api(client, other_token, recipe_id=other_recipe["id"], food_id=other_food["id"], grams="100")
    other_plan = create_plan_via_api(client, other_token, start_date="2026-04-03", days_count=1, meals_per_day=2)
    _patch_plan_slot(
        client,
        other_token,
        plan_id=other_plan["id"],
        slot_id=other_plan["slots"][0]["id"],
        payload={"recipe_id": other_recipe["id"]},
    )
    other_list = _create_shopping_list_from_plan(client, other_token, plan_id=other_plan["id"])

    response = client.post(
        "/shopping-lists/merge",
        headers=auth_headers(other_token),
        json={"shopping_list_ids": [owner_list["id"], other_list["id"]]},
    )
    assert response.status_code == 404, response.text


def test_merge_creates_materialized_list_and_filters_source_items(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="shopping_merge_full@example.com",
        username="shopping_merge_full",
    )

    food_a = _create_food_with_category(client, token, name="Merge Buckwheat", category="grains_bakery")
    food_b = _create_food_with_category(client, token, name="Merge Apples", category="fruits")

    recipe_a = create_recipe_via_api(client, token, name="Merge Recipe A", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe_a["id"], food_id=food_a["id"], grams="100")
    recipe_b = create_recipe_via_api(client, token, name="Merge Recipe B", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe_b["id"], food_id=food_a["id"], grams="50")
    add_ingredient_via_api(client, token, recipe_id=recipe_b["id"], food_id=food_b["id"], grams="20")

    plan_a = create_plan_via_api(client, token, start_date="2026-04-04", days_count=1, meals_per_day=2)
    _patch_plan_slot(client, token, plan_id=plan_a["id"], slot_id=plan_a["slots"][0]["id"], payload={"recipe_id": recipe_a["id"]})
    plan_b = create_plan_via_api(client, token, start_date="2026-04-05", days_count=1, meals_per_day=2)
    _patch_plan_slot(client, token, plan_id=plan_b["id"], slot_id=plan_b["slots"][0]["id"], payload={"recipe_id": recipe_b["id"]})

    list_a = _create_shopping_list_from_plan(client, token, plan_id=plan_a["id"], title="Первый список")
    list_a_duplicate_source = _create_shopping_list_from_plan(
        client,
        token,
        plan_id=plan_a["id"],
        title="Дубликат источника",
    )
    list_b = _create_shopping_list_from_plan(client, token, plan_id=plan_b["id"], title="Второй список")

    for item in _computed_items(list_a_duplicate_source):
        _patch_item(
            client,
            token,
            shopping_list_id=list_a_duplicate_source["id"],
            item_id=item["id"],
            payload={"checked": True},
        )

    _add_manual_item(
        client,
        token,
        shopping_list_id=list_a["id"],
        payload={"name": "Салфетки", "category": "other", "unit": "шт", "adjusted_grams": "2"},
    )
    checked_manual = _add_manual_item(
        client,
        token,
        shopping_list_id=list_a["id"],
        payload={"name": "Уже куплено", "category": "other", "unit": "шт", "adjusted_grams": "1"},
    )
    _patch_item(
        client,
        token,
        shopping_list_id=list_a["id"],
        item_id=checked_manual["id"],
        payload={"checked": True},
    )

    list_b_food_items = {item["food_id"]: item for item in _computed_items(list_b)}
    _patch_item(
        client,
        token,
        shopping_list_id=list_b["id"],
        item_id=list_b_food_items[food_a["id"]]["id"],
        payload={"adjusted_grams": "60"},
    )
    _delete_item(
        client,
        token,
        shopping_list_id=list_b["id"],
        item_id=list_b_food_items[food_b["id"]]["id"],
    )
    _add_manual_item(
        client,
        token,
        shopping_list_id=list_b["id"],
        payload={"name": "салфетки", "category": "other", "unit": "шт", "adjusted_grams": "3"},
    )

    merged = _merge_lists(
        client,
        token,
        {
            "shopping_list_ids": [list_a["id"], list_a_duplicate_source["id"], list_b["id"]],
            "title": "Общий список",
        },
    )

    assert merged["id"] not in {list_a["id"], list_a_duplicate_source["id"], list_b["id"]}
    assert merged["title"] == "Общий список"
    assert {source["plan_id"] for source in merged["sources"]} == {plan_a["id"], plan_b["id"]}

    computed_by_food = {item["food_id"]: item for item in _computed_items(merged)}
    assert set(computed_by_food) == {food_a["id"]}
    assert Decimal(str(computed_by_food[food_a["id"]]["planned_grams"])) == Decimal("160.00")
    assert computed_by_food[food_a["id"]]["adjusted_grams"] is None
    assert computed_by_food[food_a["id"]]["checked"] is False
    assert computed_by_food[food_a["id"]]["excluded"] is False

    manual_items = _manual_items(merged)
    assert len(manual_items) == 1
    manual = manual_items[0]
    assert manual["name_snapshot"] == "Салфетки"
    assert manual["category"] == "other"
    assert manual["unit"] == "шт"
    assert Decimal(str(manual["adjusted_grams"])) == Decimal("5.00")
    assert manual["checked"] is False
    assert manual["excluded"] is False

    opened = _get_shopping_list(client, token, merged["id"])
    assert opened["id"] == merged["id"]

    summaries = _list_shopping_lists(client, token)
    summary_ids = {summary["id"] for summary in summaries}
    assert {list_a["id"], list_a_duplicate_source["id"], list_b["id"], merged["id"]}.issubset(summary_ids)

    _patch_plan_slot(
        client,
        token,
        plan_id=plan_b["id"],
        slot_id=plan_b["slots"][0]["id"],
        payload={"servings_multiplier": "2"},
    )
    updated_summaries = _list_shopping_lists(client, token)
    merged_summary = next(summary for summary in updated_summaries if summary["id"] == merged["id"])
    assert merged_summary["is_outdated"] is True
