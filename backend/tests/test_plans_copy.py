from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.shopping import ShoppingListSource
from test_plans_api import (
    add_ingredient_via_api,
    auth_headers,
    create_food_via_api,
    create_plan_via_api,
    create_recipe_via_api,
    create_shopping_list_from_plan_via_api,
    create_user_with_token,
)


def _copy_plan(
    client: TestClient,
    token: str,
    *,
    plan_id: int,
    start_date: str,
    title: str | None = None,
):
    payload: dict[str, str] = {"start_date": start_date}
    if title is not None:
        payload["title"] = title
    return client.post(
        f"/plans/{plan_id}/copy",
        headers=auth_headers(token),
        json=payload,
    )


def _find_slot(plan_payload: dict, *, day_date: str, slot_index: int) -> dict:
    return next(
        slot for slot in plan_payload["slots"] if slot["day_date"] == day_date and slot["slot_index"] == slot_index
    )


def _set_slot_recipe(
    client: TestClient,
    token: str,
    *,
    plan_id: int,
    slot_id: int,
    recipe_id: int,
    servings_multiplier: str,
    pinned: bool,
) -> dict:
    response = client.patch(
        f"/plans/{plan_id}/slots/{slot_id}",
        headers=auth_headers(token),
        json={
            "recipe_id": recipe_id,
            "servings_multiplier": servings_multiplier,
            "pinned": pinned,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_user_can_copy_own_plan_with_new_id_and_start_date(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plan_copy_basic@example.com",
        username="plan_copy_basic",
    )
    source_plan = create_plan_via_api(
        client,
        token,
        start_date="2026-03-24",
        days_count=2,
        meals_per_day=3,
        title="Удачный рацион",
    )

    response = _copy_plan(
        client,
        token,
        plan_id=source_plan["id"],
        start_date="2026-04-01",
    )
    assert response.status_code == 201, response.text
    copied_plan = response.json()

    assert copied_plan["id"] != source_plan["id"]
    assert copied_plan["start_date"] == "2026-04-01"
    assert copied_plan["days_count"] == source_plan["days_count"]
    assert copied_plan["meals_per_day"] == source_plan["meals_per_day"]
    assert copied_plan["profile_id"] == source_plan["profile_id"]
    assert copied_plan["target_kcal"] == source_plan["target_kcal"]
    assert copied_plan["title"] == "Копия: Удачный рацион"


def test_copy_keeps_relative_slot_positions_recipe_and_multiplier_and_resets_pinned(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plan_copy_slots@example.com",
        username="plan_copy_slots",
    )

    food = create_food_via_api(
        client,
        token,
        name="Copy slot food",
        kcal="250",
        protein="20",
        fat="6",
        carbs="24",
        fiber="3",
    )
    recipe = create_recipe_via_api(client, token, name="Copy slot recipe", servings_count=1, meal_types=["breakfast", "dinner"])
    add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food["id"], grams="100")

    source_plan = create_plan_via_api(
        client,
        token,
        start_date="2026-03-24",
        days_count=2,
        meals_per_day=3,
        title="План со слотами",
    )
    slot_day_1_breakfast = _find_slot(source_plan, day_date="2026-03-24", slot_index=0)
    slot_day_2_dinner = _find_slot(source_plan, day_date="2026-03-25", slot_index=2)

    _set_slot_recipe(
        client,
        token,
        plan_id=source_plan["id"],
        slot_id=slot_day_1_breakfast["id"],
        recipe_id=recipe["id"],
        servings_multiplier="1.75",
        pinned=True,
    )
    _set_slot_recipe(
        client,
        token,
        plan_id=source_plan["id"],
        slot_id=slot_day_2_dinner["id"],
        recipe_id=recipe["id"],
        servings_multiplier="0.8",
        pinned=True,
    )

    copy_response = _copy_plan(
        client,
        token,
        plan_id=source_plan["id"],
        start_date="2026-04-10",
        title="Копия на апрель",
    )
    assert copy_response.status_code == 201, copy_response.text
    copied = copy_response.json()

    copied_day_1_breakfast = _find_slot(copied, day_date="2026-04-10", slot_index=0)
    copied_day_2_dinner = _find_slot(copied, day_date="2026-04-11", slot_index=2)

    assert copied_day_1_breakfast["recipe_id"] == recipe["id"]
    assert copied_day_2_dinner["recipe_id"] == recipe["id"]
    assert Decimal(str(copied_day_1_breakfast["servings_multiplier"])) == Decimal("1.75")
    assert Decimal(str(copied_day_2_dinner["servings_multiplier"])) == Decimal("0.8")
    assert copied_day_1_breakfast["pinned"] is False
    assert copied_day_2_dinner["pinned"] is False


def test_copy_does_not_copy_shopping_sources(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plan_copy_shopping@example.com",
        username="plan_copy_shopping",
    )
    source_plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2, title="План")
    shopping = create_shopping_list_from_plan_via_api(client, token, plan_id=source_plan["id"])
    assert len(shopping["sources"]) == 1

    copy_response = _copy_plan(client, token, plan_id=source_plan["id"], start_date="2026-03-31")
    assert copy_response.status_code == 201, copy_response.text
    copied_plan_id = copy_response.json()["id"]

    with db_session_factory() as db:
        copied_sources = db.execute(
            select(ShoppingListSource).where(ShoppingListSource.plan_id == copied_plan_id)
        ).scalars().all()

    assert copied_sources == []


def test_copy_copies_slot_ingredient_overrides(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plan_copy_overrides@example.com",
        username="plan_copy_overrides",
    )

    food_a = create_food_via_api(
        client,
        token,
        name="Override A",
        kcal="100",
        protein="8",
        fat="2",
        carbs="12",
        fiber="1",
    )
    food_b = create_food_via_api(
        client,
        token,
        name="Override B",
        kcal="120",
        protein="10",
        fat="3",
        carbs="14",
        fiber="2",
    )

    recipe = create_recipe_via_api(client, token, name="Override recipe", servings_count=2, meal_types=["lunch"])
    add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food_a["id"], grams="200")

    recipe_read_response = client.get(f"/recipes/{recipe['id']}", headers=auth_headers(token))
    assert recipe_read_response.status_code == 200, recipe_read_response.text
    ingredient = recipe_read_response.json()["ingredients"][0]

    source_plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    source_slot = _find_slot(source_plan, day_date="2026-03-24", slot_index=0)

    set_slot = _set_slot_recipe(
        client,
        token,
        plan_id=source_plan["id"],
        slot_id=source_slot["id"],
        recipe_id=recipe["id"],
        servings_multiplier="1",
        pinned=False,
    )
    assert set_slot["recipe_id"] == recipe["id"]

    put_override = client.put(
        f"/plans/{source_plan['id']}/slots/{source_slot['id']}/ingredient-overrides",
        headers=auth_headers(token),
        json={
            "base_overrides": [
                {
                    "recipe_ingredient_id": ingredient["id"],
                    "food_id": food_b["id"],
                    "grams": "150",
                    "is_excluded": False,
                }
            ],
            "manual_items": [
                {
                    "food_id": food_b["id"],
                    "grams": "30",
                }
            ],
        },
    )
    assert put_override.status_code == 200, put_override.text
    assert put_override.json()["has_overrides"] is True

    copy_response = _copy_plan(client, token, plan_id=source_plan["id"], start_date="2026-04-24")
    assert copy_response.status_code == 201, copy_response.text
    copied = copy_response.json()
    copied_slot = _find_slot(copied, day_date="2026-04-24", slot_index=0)

    copied_ingredients = client.get(
        f"/plans/{copied['id']}/slots/{copied_slot['id']}/ingredients",
        headers=auth_headers(token),
    )
    assert copied_ingredients.status_code == 200, copied_ingredients.text
    payload = copied_ingredients.json()
    assert payload["has_overrides"] is True
    assert any(item["source"] == "overridden" for item in payload["items"])
    assert any(item["source"] == "manual" for item in payload["items"])


def test_copy_forbidden_for_another_user_plan_returns_404(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="plan_copy_owner@example.com",
        username="plan_copy_owner",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="plan_copy_other@example.com",
        username="plan_copy_other",
    )
    source_plan = create_plan_via_api(client, owner_token, start_date="2026-03-24", days_count=1, meals_per_day=2)

    response = _copy_plan(client, other_token, plan_id=source_plan["id"], start_date="2026-04-01")
    assert response.status_code == 404, response.text


def test_copy_blank_title_falls_back_to_copy_default(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plan_copy_blank_title@example.com",
        username="plan_copy_blank_title",
    )
    source_plan = create_plan_via_api(
        client,
        token,
        start_date="2026-03-24",
        days_count=1,
        meals_per_day=2,
        title="Оригинальный план",
    )

    response = _copy_plan(
        client,
        token,
        plan_id=source_plan["id"],
        start_date="2026-04-01",
        title="   ",
    )
    assert response.status_code == 201, response.text
    copied = response.json()
    assert copied["title"] == "Копия: Оригинальный план"
