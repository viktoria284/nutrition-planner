from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.models.enums import FoodSource, FoodStatus
from app.models.foods import FoodItem
from test_plans_api import (
    add_ingredient_via_api,
    auth_headers,
    create_food_via_api,
    create_plan_via_api,
    create_recipe_via_api,
    create_user_with_token,
)


def _create_verified_food(db_session_factory: sessionmaker[Session], *, name: str) -> FoodItem:
    db = db_session_factory()
    try:
        item = FoodItem(
            name=name,
            brand=None,
            category="other",
            kcal=Decimal("100"),
            protein=Decimal("10"),
            fat=Decimal("5"),
            carbs=Decimal("10"),
            fiber=Decimal("1"),
            source=FoodSource.verified,
            status=FoodStatus.approved,
            owner_user_id=None,
            is_listed=True,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        db.expunge(item)
        return item
    finally:
        db.close()


def _add_to_pantry(client: TestClient, token: str, food_id: int) -> dict:
    response = client.post("/pantry", headers=auth_headers(token), json={"food_id": food_id})
    assert response.status_code == 201, response.text
    return response.json()


def _delete_from_pantry(client: TestClient, token: str, food_id: int) -> None:
    response = client.delete(f"/pantry/{food_id}", headers=auth_headers(token))
    assert response.status_code == 204, response.text


def _list_pantry(client: TestClient, token: str) -> list[dict]:
    response = client.get("/pantry", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


def _create_shopping_list_from_plan(client: TestClient, token: str, plan_id: int) -> dict:
    response = client.post(
        "/shopping-lists/from-plan",
        headers=auth_headers(token),
        json={"plan_id": plan_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _rebuild_shopping_list(client: TestClient, token: str, shopping_list_id: int) -> dict:
    response = client.post(
        f"/shopping-lists/{shopping_list_id}/rebuild",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _patch_shopping_item(client: TestClient, token: str, shopping_list_id: int, item_id: int, payload: dict) -> dict:
    response = client.patch(
        f"/shopping-lists/{shopping_list_id}/items/{item_id}",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _build_plan_with_recipe_foods(client: TestClient, token: str, *, food_ids: list[int]) -> dict:
    recipe = create_recipe_via_api(client, token, name="Pantry recipe", servings_count=1)
    for food_id in food_ids:
        add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food_id, grams="100")

    plan = create_plan_via_api(client, token, start_date="2026-05-18", days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]
    patch_slot = client.patch(
        f"/plans/{plan['id']}/slots/{slot_id}",
        headers=auth_headers(token),
        json={"recipe_id": recipe["id"], "servings_multiplier": "1"},
    )
    assert patch_slot.status_code == 200, patch_slot.text
    return plan


def test_get_pantry_returns_only_current_user_items(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user_a, token_a = create_user_with_token(
        db_session_factory,
        email="pantry_list_a@example.com",
        username="pantry_list_a",
    )
    _user_b, token_b = create_user_with_token(
        db_session_factory,
        email="pantry_list_b@example.com",
        username="pantry_list_b",
    )
    food_a = create_food_via_api(
        client,
        token_a,
        name="Паприка",
        kcal="10",
        protein="0.5",
        fat="0.2",
        carbs="2",
        fiber="1",
    )
    food_b = create_food_via_api(
        client,
        token_b,
        name="Корица",
        kcal="20",
        protein="0.3",
        fat="0.1",
        carbs="5",
        fiber="2",
    )

    _add_to_pantry(client, token_a, food_a["id"])
    _add_to_pantry(client, token_b, food_b["id"])

    listed_a = _list_pantry(client, token_a)
    assert len(listed_a) == 1
    assert listed_a[0]["food_id"] == food_a["id"]


def test_post_pantry_allows_verified_and_own_private_foods_and_is_idempotent(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="pantry_access@example.com",
        username="pantry_access",
    )
    verified = _create_verified_food(db_session_factory, name="Рис круглозёрный")
    own_private = create_food_via_api(
        client,
        token,
        name="Домашний соус",
        kcal="150",
        protein="3",
        fat="10",
        carbs="8",
        fiber="1",
    )

    first_verified = _add_to_pantry(client, token, verified.id)
    second_verified = _add_to_pantry(client, token, verified.id)
    assert first_verified["food_id"] == verified.id
    assert second_verified["food_id"] == verified.id

    private_added = _add_to_pantry(client, token, own_private["id"])
    assert private_added["food_id"] == own_private["id"]

    listed = _list_pantry(client, token)
    assert {item["food_id"] for item in listed} == {verified.id, own_private["id"]}


def test_pantry_rejects_foreign_private_food(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="pantry_owner@example.com",
        username="pantry_owner",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="pantry_other@example.com",
        username="pantry_other",
    )
    owner_food = create_food_via_api(
        client,
        owner_token,
        name="Личное масло",
        kcal="899",
        protein="0",
        fat="99.9",
        carbs="0",
        fiber="0",
    )

    response = client.post("/pantry", headers=auth_headers(other_token), json={"food_id": owner_food["id"]})
    assert response.status_code == 404, response.text


def test_delete_pantry_is_idempotent(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="pantry_delete@example.com",
        username="pantry_delete",
    )
    food = create_food_via_api(
        client,
        token,
        name="Соль",
        kcal="0",
        protein="0",
        fat="0",
        carbs="0",
        fiber="0",
    )

    _add_to_pantry(client, token, food["id"])
    _delete_from_pantry(client, token, food["id"])
    _delete_from_pantry(client, token, food["id"])
    assert _list_pantry(client, token) == []


def test_rebuild_preserves_manual_move_to_main_list(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="pantry_preserve@example.com",
        username="pantry_preserve",
    )
    food_pantry = create_food_via_api(
        client,
        token,
        name="Лук репчатый",
        kcal="40",
        protein="1.1",
        fat="0.1",
        carbs="9.3",
        fiber="1.7",
    )
    food_regular = create_food_via_api(
        client,
        token,
        name="Курица",
        kcal="165",
        protein="31",
        fat="3.6",
        carbs="0",
        fiber="0",
    )

    _add_to_pantry(client, token, food_pantry["id"])
    plan = _build_plan_with_recipe_foods(client, token, food_ids=[food_pantry["id"], food_regular["id"]])

    shopping_list = _create_shopping_list_from_plan(client, token, plan["id"])
    pantry_item = next(item for item in shopping_list["items"] if item["food_id"] == food_pantry["id"])
    assert pantry_item["in_pantry_section"] is True

    patched = _patch_shopping_item(
        client,
        token,
        shopping_list["id"],
        pantry_item["id"],
        {"in_pantry_section": False},
    )
    assert patched["in_pantry_section"] is False

    rebuilt = _rebuild_shopping_list(client, token, shopping_list["id"])
    rebuilt_pantry_item = next(item for item in rebuilt["items"] if item["food_id"] == food_pantry["id"])
    assert rebuilt_pantry_item["in_pantry_section"] is False
    assert any(item["food_id"] == food_pantry["id"] for item in _list_pantry(client, token))


def test_remove_from_home_updates_current_and_future_lists(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="pantry_remove_home@example.com",
        username="pantry_remove_home",
    )
    food = create_food_via_api(
        client,
        token,
        name="Чеснок",
        kcal="149",
        protein="6.4",
        fat="0.5",
        carbs="33",
        fiber="2.1",
    )
    _add_to_pantry(client, token, food["id"])
    plan = _build_plan_with_recipe_foods(client, token, food_ids=[food["id"]])

    shopping_list = _create_shopping_list_from_plan(client, token, plan["id"])
    pantry_item = next(item for item in shopping_list["items"] if item["food_id"] == food["id"])
    assert pantry_item["in_pantry_section"] is True

    _delete_from_pantry(client, token, food["id"])
    patched = _patch_shopping_item(
        client,
        token,
        shopping_list["id"],
        pantry_item["id"],
        {"in_pantry_section": False},
    )
    assert patched["in_pantry_section"] is False
    assert _list_pantry(client, token) == []

    rebuilt = _rebuild_shopping_list(client, token, shopping_list["id"])
    rebuilt_item = next(item for item in rebuilt["items"] if item["food_id"] == food["id"])
    assert rebuilt_item["in_pantry_section"] is False

    next_list = _create_shopping_list_from_plan(client, token, plan["id"])
    next_item = next(item for item in next_list["items"] if item["food_id"] == food["id"])
    assert next_item["in_pantry_section"] is False


def test_mark_as_home_updates_current_and_future_lists(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="pantry_mark_home@example.com",
        username="pantry_mark_home",
    )
    food = create_food_via_api(
        client,
        token,
        name="Оливковое масло",
        kcal="884",
        protein="0",
        fat="100",
        carbs="0",
        fiber="0",
    )
    plan = _build_plan_with_recipe_foods(client, token, food_ids=[food["id"]])

    shopping_list = _create_shopping_list_from_plan(client, token, plan["id"])
    item = next(entry for entry in shopping_list["items"] if entry["food_id"] == food["id"])
    assert item["in_pantry_section"] is False

    _add_to_pantry(client, token, food["id"])
    patched = _patch_shopping_item(client, token, shopping_list["id"], item["id"], {"in_pantry_section": True})
    assert patched["in_pantry_section"] is True

    next_list = _create_shopping_list_from_plan(client, token, plan["id"])
    next_item = next(entry for entry in next_list["items"] if entry["food_id"] == food["id"])
    assert next_item["in_pantry_section"] is True
