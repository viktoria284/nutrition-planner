from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.plan_slot import PlanSlot
from app.models.profile import Profile
from app.models.shopping import ShoppingListSource
from app.models.user import User
from app.services.recipes import seed_demo_public_recipes
from app.services.security import create_access_token


def create_user_with_token(
    db_session_factory: sessionmaker[Session],
    *,
    email: str,
    username: str,
) -> tuple[User, str]:
    db_session = db_session_factory()
    try:
        user = User(
            email=email,
            username=username,
            hashed_password="test_hashed_password",
        )
        db_session.add(user)
        db_session.flush()
        user_id = user.id

        profile = Profile(
            user_id=user_id,
            name="Test Default Profile",
            target_kcal=2000,
            target_protein=None,
            target_fat=None,
            target_carbs=None,
            target_fiber=None,
        )
        db_session.add(profile)
        db_session.commit()
        db_session.refresh(user)
        db_session.expunge(user)
    finally:
        db_session.close()

    token = create_access_token(str(user_id))
    return user, token


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_plan_via_api(
    client: TestClient,
    token: str,
    *,
    start_date: str = "2026-03-24",
    days_count: int = 3,
    meals_per_day: int = 3,
    profile_id: int | None = None,
    title: str | None = "Тестовый план",
) -> dict:
    resolved_profile_id = profile_id
    if resolved_profile_id is None:
        profiles_response = client.get("/profiles", headers=auth_headers(token))
        assert profiles_response.status_code == 200, profiles_response.text
        profiles_payload = profiles_response.json()
        assert len(profiles_payload) > 0
        resolved_profile_id = profiles_payload[0]["id"]

    response = client.post(
        "/plans",
        headers=auth_headers(token),
        json={
            "start_date": start_date,
            "days_count": days_count,
            "meals_per_day": meals_per_day,
            "profile_id": resolved_profile_id,
            "title": title,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_shopping_list_from_plan_via_api(
    client: TestClient,
    token: str,
    *,
    plan_id: int,
    title: str | None = None,
) -> dict:
    payload: dict[str, object] = {"plan_id": plan_id}
    if title is not None:
        payload["title"] = title

    response = client.post(
        "/shopping-lists/from-plan",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_recipe_via_api(
    client: TestClient,
    token: str,
    *,
    name: str = "Тестовый рецепт",
    servings_count: int = 2,
    meal_types: list[str] | None = None,
) -> dict:
    response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json={
            "name": name,
            "servings_count": servings_count,
            "meal_types": meal_types or ["breakfast"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_food_via_api(
    client: TestClient,
    token: str,
    *,
    name: str,
    kcal: str,
    protein: str,
    fat: str,
    carbs: str,
    fiber: str | None = None,
) -> dict:
    payload: dict[str, str] = {
        "name": name,
        "kcal": kcal,
        "protein": protein,
        "fat": fat,
        "carbs": carbs,
    }
    if fiber is not None:
        payload["fiber"] = fiber

    response = client.post(
        "/foods",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_ingredient_via_api(
    client: TestClient,
    token: str,
    *,
    recipe_id: int,
    food_id: int,
    grams: str,
) -> dict:
    response = client.post(
        f"/recipes/{recipe_id}/ingredients",
        headers=auth_headers(token),
        json={
            "food_id": food_id,
            "grams": grams,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def publish_recipe_via_api(client: TestClient, token: str, recipe_id: int) -> dict:
    response = client.post(
        f"/recipes/{recipe_id}/publish",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def withdraw_recipe_via_api(client: TestClient, token: str, recipe_id: int) -> dict:
    response = client.post(
        f"/recipes/{recipe_id}/withdraw",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_get_plans_returns_only_current_user_plans(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    user1, token_user1 = create_user_with_token(
        db_session_factory,
        email="plans_user1@example.com",
        username="plans_user1",
    )
    _user2, token_user2 = create_user_with_token(
        db_session_factory,
        email="plans_user2@example.com",
        username="plans_user2",
    )

    plan_user1 = create_plan_via_api(client, token_user1, title="User 1 Plan")
    plan_user2 = create_plan_via_api(client, token_user2, title="User 2 Plan")

    response = client.get("/plans", headers=auth_headers(token_user1))
    assert response.status_code == 200, response.text

    plans = response.json()
    returned_ids = {plan["id"] for plan in plans}
    assert plan_user1["id"] in returned_ids
    assert plan_user2["id"] not in returned_ids
    assert all(plan["owner_user_id"] == user1.id for plan in plans)


def test_get_plans_includes_profile_snapshot_fields_for_autogenerated_plan(
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
        email="plans_list_profile_snapshot@example.com",
        username="plans_list_profile_snapshot",
    )

    autogen = client.post(
        "/plans/autogenerate",
        headers=auth_headers(token),
        json={
            "start_date": "2026-05-02",
            "days_count": 2,
            "meals_per_day": 3,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert autogen.status_code == 201, autogen.text

    response = client.get("/plans", headers=auth_headers(token))
    assert response.status_code == 200, response.text

    items = response.json()
    assert len(items) >= 1
    item = next((plan for plan in items if plan["id"] == autogen.json()["id"]), None)
    assert item is not None
    assert item["profile_id"] is not None
    assert item["profile_name"] == "Test Default Profile"
    assert item["target_kcal"] == 2000
    assert "target_protein" in item
    assert "target_fat" in item
    assert "target_carbs" in item
    assert "target_fiber" in item


def test_post_plan_creates_expected_slots(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_create@example.com",
        username="plans_create",
    )
    plan = create_plan_via_api(
        client,
        token,
        start_date="2026-03-24",
        days_count=3,
        meals_per_day=4,
    )
    slots = plan["slots"]

    assert len(slots) == 12

    pairs = [(slot["day_date"], slot["slot_index"]) for slot in slots]
    assert pairs == sorted(pairs)

    expected_dates = ["2026-03-24", "2026-03-25", "2026-03-26"]
    for day_date in expected_dates:
        day_slots = [slot for slot in slots if slot["day_date"] == day_date]
        assert len(day_slots) == 4
        assert [slot["slot_index"] for slot in day_slots] == [0, 1, 2, 3]
        assert all(slot["recipe_id"] is None for slot in day_slots)
        assert all(Decimal(str(slot["servings_multiplier"])) == Decimal("1") for slot in day_slots)
        assert all(slot["pinned"] is False for slot in day_slots)


def test_post_plan_manual_create_saves_profile_and_targets_snapshot(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_manual_profile_snapshot@example.com",
        username="plans_manual_profile_snapshot",
    )

    profile_create_response = client.post(
        "/profiles",
        headers=auth_headers(token),
        json={
            "name": "Набор массы",
            "target_kcal": 3150,
            "target_protein": 185,
            "target_fat": 95,
            "target_carbs": 360,
            "target_fiber": 32,
        },
    )
    assert profile_create_response.status_code == 201, profile_create_response.text
    profile = profile_create_response.json()

    created = create_plan_via_api(
        client,
        token,
        start_date="2026-03-24",
        days_count=2,
        meals_per_day=3,
        profile_id=profile["id"],
        title="Ручной план с профилем",
    )

    assert created["profile_id"] == profile["id"]
    assert created["profile_name"] == "Набор массы"
    assert created["target_kcal"] == 3150
    assert created["target_protein"] == 185
    assert created["target_fat"] == 95
    assert created["target_carbs"] == 360
    assert created["target_fiber"] == 32

    get_response = client.get(f"/plans/{created['id']}", headers=auth_headers(token))
    assert get_response.status_code == 200, get_response.text
    payload = get_response.json()
    assert payload["profile_id"] == profile["id"]
    assert payload["profile_name"] == "Набор массы"
    assert payload["target_kcal"] == 3150
    assert payload["target_protein"] == 185
    assert payload["target_fat"] == 95
    assert payload["target_carbs"] == 360
    assert payload["target_fiber"] == 32


def test_post_plan_returns_404_for_foreign_profile_id(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="plans_manual_profile_owner@example.com",
        username="plans_manual_profile_owner",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="plans_manual_profile_other@example.com",
        username="plans_manual_profile_other",
    )

    other_profiles = client.get("/profiles", headers=auth_headers(other_token))
    assert other_profiles.status_code == 200, other_profiles.text
    foreign_profile_id = other_profiles.json()[0]["id"]

    response = client.post(
        "/plans",
        headers=auth_headers(owner_token),
        json={
            "start_date": "2026-03-24",
            "days_count": 3,
            "meals_per_day": 3,
            "profile_id": foreign_profile_id,
            "title": "Нельзя с чужим профилем",
        },
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Profile not found"


def test_post_plan_requires_profile_id(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_manual_profile_required@example.com",
        username="plans_manual_profile_required",
    )

    response = client.post(
        "/plans",
        headers=auth_headers(token),
        json={
            "start_date": "2026-03-24",
            "days_count": 3,
            "meals_per_day": 3,
            "title": "Без профиля",
        },
    )
    assert response.status_code == 422, response.text
    assert any(err["loc"][-1] == "profile_id" for err in response.json().get("detail", []))


def test_post_plan_rejects_meals_per_day_below_min(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_invalid_meals@example.com",
        username="plans_invalid_meals",
    )
    profiles_response = client.get("/profiles", headers=auth_headers(token))
    assert profiles_response.status_code == 200, profiles_response.text
    profile_id = profiles_response.json()[0]["id"]

    response = client.post(
        "/plans",
        headers=auth_headers(token),
        json={
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 1,
            "profile_id": profile_id,
            "title": "invalid",
        },
    )
    assert response.status_code == 422, response.text
    assert any(err["loc"][-1] == "meals_per_day" for err in response.json().get("detail", []))


def test_get_plan_day_totals_with_two_slots_and_multiplier(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_totals_main@example.com",
        username="plans_totals_main",
    )

    food_a = create_food_via_api(
        client,
        token,
        name="Totals Food A",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
        fiber="6.00",
    )
    food_b = create_food_via_api(
        client,
        token,
        name="Totals Food B",
        kcal="50.00",
        protein="5.00",
        fat="2.00",
        carbs="8.00",
        fiber="4.00",
    )

    recipe_a = create_recipe_via_api(client, token, name="Totals Recipe A", servings_count=1)
    recipe_b = create_recipe_via_api(client, token, name="Totals Recipe B", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe_a["id"], food_id=food_a["id"], grams="100")
    add_ingredient_via_api(client, token, recipe_id=recipe_b["id"], food_id=food_b["id"], grams="100")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    first_slot_id = plan["slots"][0]["id"]
    second_slot_id = plan["slots"][1]["id"]

    patch_first = client.patch(
        f"/plans/{plan['id']}/slots/{first_slot_id}",
        headers=auth_headers(token),
        json={"recipe_id": recipe_a["id"], "servings_multiplier": "1.5"},
    )
    assert patch_first.status_code == 200, patch_first.text

    patch_second = client.patch(
        f"/plans/{plan['id']}/slots/{second_slot_id}",
        headers=auth_headers(token),
        json={"recipe_id": recipe_b["id"]},
    )
    assert patch_second.status_code == 200, patch_second.text

    response = client.get(f"/plans/{plan['id']}", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["days"]) == 1

    day = payload["days"][0]
    assert day["date"] == "2026-03-24"
    assert [slot["slot_index"] for slot in day["slots"]] == [0, 1]

    totals = day["totals"]
    assert Decimal(str(totals["kcal"])) == Decimal("200.00")
    assert Decimal(str(totals["protein"])) == Decimal("20.00")
    assert Decimal(str(totals["fat"])) == Decimal("9.50")
    assert Decimal(str(totals["carbs"])) == Decimal("38.00")
    assert Decimal(str(totals["fiber"])) == Decimal("13.00")


def test_get_plan_slot_totals_reflect_recipe_multiplier(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_slot_totals@example.com",
        username="plans_slot_totals",
    )

    food = create_food_via_api(
        client,
        token,
        name="Slot Totals Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
        fiber="6.00",
    )
    recipe = create_recipe_via_api(client, token, name="Slot Totals Recipe", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food["id"], grams="100")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    first_slot_id = plan["slots"][0]["id"]
    second_slot_id = plan["slots"][1]["id"]

    set_first = client.patch(
        f"/plans/{plan['id']}/slots/{first_slot_id}",
        headers=auth_headers(token),
        json={"recipe_id": recipe["id"], "servings_multiplier": "1.5"},
    )
    assert set_first.status_code == 200, set_first.text
    set_second = client.patch(
        f"/plans/{plan['id']}/slots/{second_slot_id}",
        headers=auth_headers(token),
        json={"recipe_id": None},
    )
    assert set_second.status_code == 200, set_second.text

    get_response = client.get(f"/plans/{plan['id']}", headers=auth_headers(token))
    assert get_response.status_code == 200, get_response.text
    payload = get_response.json()
    first_slot = payload["days"][0]["slots"][0]
    second_slot = payload["days"][0]["slots"][1]

    assert Decimal(str(first_slot["slot_kcal"])) == Decimal("150.00")
    assert Decimal(str(first_slot["slot_protein"])) == Decimal("15.00")
    assert Decimal(str(first_slot["slot_fat"])) == Decimal("7.50")
    assert Decimal(str(first_slot["slot_carbs"])) == Decimal("30.00")
    assert Decimal(str(first_slot["slot_fiber"])) == Decimal("9.00")

    assert Decimal(str(second_slot["slot_kcal"])) == Decimal("0.00")
    assert Decimal(str(second_slot["slot_protein"])) == Decimal("0.00")
    assert Decimal(str(second_slot["slot_fat"])) == Decimal("0.00")
    assert Decimal(str(second_slot["slot_carbs"])) == Decimal("0.00")
    assert Decimal(str(second_slot["slot_fiber"])) == Decimal("0.00")


def test_autogenerated_plan_read_includes_profile_snapshot_fields(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_autogen_profile_fields@example.com",
        username="plans_autogen_profile_fields",
    )

    lunch_food = create_food_via_api(
        client,
        token,
        name="Autogen Profile Fields Lunch Food",
        kcal="200.00",
        protein="15.00",
        fat="8.00",
        carbs="20.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Autogen Profile Fields Dinner Food",
        kcal="220.00",
        protein="18.00",
        fat="9.00",
        carbs="22.00",
    )
    lunch_recipe = create_recipe_via_api(
        client,
        token,
        name="Autogen Profile Fields Lunch Recipe",
        servings_count=1,
        meal_types=["lunch"],
    )
    dinner_recipe = create_recipe_via_api(
        client,
        token,
        name="Autogen Profile Fields Dinner Recipe",
        servings_count=1,
        meal_types=["dinner"],
    )
    add_ingredient_via_api(client, token, recipe_id=lunch_recipe["id"], food_id=lunch_food["id"], grams="100")
    add_ingredient_via_api(client, token, recipe_id=dinner_recipe["id"], food_id=dinner_food["id"], grams="100")

    response = client.post(
        "/plans/autogenerate",
        headers=auth_headers(token),
        json={
            "start_date": "2026-03-24",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()

    assert payload["profile_id"] is not None
    assert payload["profile_name"] == "Test Default Profile"
    assert payload["target_kcal"] == 2000
    assert payload["target_protein"] is None
    assert payload["target_fat"] is None
    assert payload["target_carbs"] is None
    assert payload["target_fiber"] is None


def test_autogenerate_without_title_uses_default_title(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_autogen_default_title@example.com",
        username="plans_autogen_default_title",
    )

    lunch_food = create_food_via_api(
        client,
        token,
        name="Autogen Default Title Lunch Food",
        kcal="200.00",
        protein="15.00",
        fat="8.00",
        carbs="20.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Autogen Default Title Dinner Food",
        kcal="220.00",
        protein="18.00",
        fat="9.00",
        carbs="22.00",
    )
    lunch_recipe = create_recipe_via_api(
        client,
        token,
        name="Autogen Default Title Lunch Recipe",
        servings_count=1,
        meal_types=["lunch"],
    )
    dinner_recipe = create_recipe_via_api(
        client,
        token,
        name="Autogen Default Title Dinner Recipe",
        servings_count=1,
        meal_types=["dinner"],
    )
    add_ingredient_via_api(client, token, recipe_id=lunch_recipe["id"], food_id=lunch_food["id"], grams="100")
    add_ingredient_via_api(client, token, recipe_id=dinner_recipe["id"], food_id=dinner_food["id"], grams="100")

    response = client.post(
        "/plans/autogenerate",
        headers=auth_headers(token),
        json={
            "start_date": "2026-05-12",
            "days_count": 1,
            "meals_per_day": 2,
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["title"] == "План с 12 мая 2026 г."


def test_autogenerate_with_custom_title_stores_trimmed_value(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_autogen_custom_title@example.com",
        username="plans_autogen_custom_title",
    )

    lunch_food = create_food_via_api(
        client,
        token,
        name="Autogen Custom Title Lunch Food",
        kcal="200.00",
        protein="15.00",
        fat="8.00",
        carbs="20.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Autogen Custom Title Dinner Food",
        kcal="220.00",
        protein="18.00",
        fat="9.00",
        carbs="22.00",
    )
    lunch_recipe = create_recipe_via_api(
        client,
        token,
        name="Autogen Custom Title Lunch Recipe",
        servings_count=1,
        meal_types=["lunch"],
    )
    dinner_recipe = create_recipe_via_api(
        client,
        token,
        name="Autogen Custom Title Dinner Recipe",
        servings_count=1,
        meal_types=["dinner"],
    )
    add_ingredient_via_api(client, token, recipe_id=lunch_recipe["id"], food_id=lunch_food["id"], grams="100")
    add_ingredient_via_api(client, token, recipe_id=dinner_recipe["id"], food_id=dinner_food["id"], grams="100")

    response = client.post(
        "/plans/autogenerate",
        headers=auth_headers(token),
        json={
            "start_date": "2026-05-12",
            "days_count": 1,
            "meals_per_day": 2,
            "title": "  Рацион на неделю  ",
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["title"] == "Рацион на неделю"


def test_autogenerate_with_blank_title_uses_default_title(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_autogen_blank_title@example.com",
        username="plans_autogen_blank_title",
    )

    lunch_food = create_food_via_api(
        client,
        token,
        name="Autogen Blank Title Lunch Food",
        kcal="200.00",
        protein="15.00",
        fat="8.00",
        carbs="20.00",
    )
    dinner_food = create_food_via_api(
        client,
        token,
        name="Autogen Blank Title Dinner Food",
        kcal="220.00",
        protein="18.00",
        fat="9.00",
        carbs="22.00",
    )
    lunch_recipe = create_recipe_via_api(
        client,
        token,
        name="Autogen Blank Title Lunch Recipe",
        servings_count=1,
        meal_types=["lunch"],
    )
    dinner_recipe = create_recipe_via_api(
        client,
        token,
        name="Autogen Blank Title Dinner Recipe",
        servings_count=1,
        meal_types=["dinner"],
    )
    add_ingredient_via_api(client, token, recipe_id=lunch_recipe["id"], food_id=lunch_food["id"], grams="100")
    add_ingredient_via_api(client, token, recipe_id=dinner_recipe["id"], food_id=dinner_food["id"], grams="100")

    response = client.post(
        "/plans/autogenerate",
        headers=auth_headers(token),
        json={
            "start_date": "2026-05-12",
            "days_count": 1,
            "meals_per_day": 2,
            "title": "   ",
            "use_public_recipes": True,
            "excluded_recipe_ids": [],
            "excluded_food_ids": [],
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["title"] == "План с 12 мая 2026 г."


def test_get_plan_day_totals_empty_or_null_recipe_slots_are_zero(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_totals_empty@example.com",
        username="plans_totals_empty",
    )

    food = create_food_via_api(
        client,
        token,
        name="Totals Food Empty",
        kcal="80.00",
        protein="8.00",
        fat="4.00",
        carbs="16.00",
    )
    recipe = create_recipe_via_api(client, token, name="Totals Recipe Empty", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food["id"], grams="100")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]

    set_recipe = client.patch(
        f"/plans/{plan['id']}/slots/{slot_id}",
        headers=auth_headers(token),
        json={"recipe_id": recipe["id"]},
    )
    assert set_recipe.status_code == 200, set_recipe.text

    with_recipe = client.get(f"/plans/{plan['id']}", headers=auth_headers(token))
    assert with_recipe.status_code == 200, with_recipe.text
    with_recipe_totals = with_recipe.json()["days"][0]["totals"]
    assert Decimal(str(with_recipe_totals["kcal"])) == Decimal("80.00")
    assert Decimal(str(with_recipe_totals["protein"])) == Decimal("8.00")
    assert Decimal(str(with_recipe_totals["fat"])) == Decimal("4.00")
    assert Decimal(str(with_recipe_totals["carbs"])) == Decimal("16.00")

    clear_recipe = client.patch(
        f"/plans/{plan['id']}/slots/{slot_id}",
        headers=auth_headers(token),
        json={"recipe_id": None},
    )
    assert clear_recipe.status_code == 200, clear_recipe.text

    without_recipe = client.get(f"/plans/{plan['id']}", headers=auth_headers(token))
    assert without_recipe.status_code == 200, without_recipe.text
    day = without_recipe.json()["days"][0]
    totals = day["totals"]
    assert Decimal(str(totals["kcal"])) == Decimal("0.00")
    assert Decimal(str(totals["protein"])) == Decimal("0.00")
    assert Decimal(str(totals["fat"])) == Decimal("0.00")
    assert Decimal(str(totals["carbs"])) == Decimal("0.00")
    assert day["slots"][0]["recipe_id"] is None


def test_get_plan_day_totals_rounding_is_stable(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_totals_rounding@example.com",
        username="plans_totals_rounding",
    )

    food = create_food_via_api(
        client,
        token,
        name="Totals Food Rounding",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="2.50",
    )
    recipe = create_recipe_via_api(client, token, name="Totals Recipe Rounding", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food["id"], grams="100")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]
    set_recipe = client.patch(
        f"/plans/{plan['id']}/slots/{slot_id}",
        headers=auth_headers(token),
        json={"recipe_id": recipe["id"], "servings_multiplier": "1.333"},
    )
    assert set_recipe.status_code == 200, set_recipe.text

    response = client.get(f"/plans/{plan['id']}", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    totals = response.json()["days"][0]["totals"]
    assert Decimal(str(totals["kcal"])) == Decimal("133.30")
    assert Decimal(str(totals["protein"])) == Decimal("13.33")
    assert Decimal(str(totals["fat"])) == Decimal("6.67")
    assert Decimal(str(totals["carbs"])) == Decimal("3.33")


def test_get_plan_day_totals_recalculate_after_multiplier_update(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_totals_recalc@example.com",
        username="plans_totals_recalc",
    )

    food = create_food_via_api(
        client,
        token,
        name="Totals Recalc Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="20.00",
    )
    recipe = create_recipe_via_api(client, token, name="Totals Recalc Recipe", servings_count=1)
    add_ingredient_via_api(client, token, recipe_id=recipe["id"], food_id=food["id"], grams="100")

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]

    initial_set = client.patch(
        f"/plans/{plan['id']}/slots/{slot_id}",
        headers=auth_headers(token),
        json={"recipe_id": recipe["id"], "servings_multiplier": "1"},
    )
    assert initial_set.status_code == 200, initial_set.text

    initial_get = client.get(f"/plans/{plan['id']}", headers=auth_headers(token))
    assert initial_get.status_code == 200, initial_get.text
    initial_totals = initial_get.json()["days"][0]["totals"]
    assert Decimal(str(initial_totals["kcal"])) == Decimal("100.00")
    assert Decimal(str(initial_totals["protein"])) == Decimal("10.00")

    update_multiplier = client.patch(
        f"/plans/{plan['id']}/slots/{slot_id}",
        headers=auth_headers(token),
        json={"servings_multiplier": "2.5"},
    )
    assert update_multiplier.status_code == 200, update_multiplier.text

    recalculated_get = client.get(f"/plans/{plan['id']}", headers=auth_headers(token))
    assert recalculated_get.status_code == 200, recalculated_get.text
    recalculated_totals = recalculated_get.json()["days"][0]["totals"]
    assert Decimal(str(recalculated_totals["kcal"])) == Decimal("250.00")
    assert Decimal(str(recalculated_totals["protein"])) == Decimal("25.00")
    assert Decimal(str(recalculated_totals["fat"])) == Decimal("12.50")
    assert Decimal(str(recalculated_totals["carbs"])) == Decimal("50.00")


def test_get_plan_empty_plan_day_totals_are_zero(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_empty_scenario@example.com",
        username="plans_empty_scenario",
    )

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2)
    response = client.get(f"/plans/{plan['id']}", headers=auth_headers(token))
    assert response.status_code == 200, response.text

    payload = response.json()
    assert len(payload["days"]) == 1
    assert len(payload["days"][0]["slots"]) == 2

    totals = payload["days"][0]["totals"]
    assert Decimal(str(totals["kcal"])) == Decimal("0.00")
    assert Decimal(str(totals["protein"])) == Decimal("0.00")
    assert Decimal(str(totals["fat"])) == Decimal("0.00")
    assert Decimal(str(totals["carbs"])) == Decimal("0.00")


def test_get_plan_owner_only(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, token_owner = create_user_with_token(
        db_session_factory,
        email="plans_get_owner@example.com",
        username="plans_get_owner",
    )
    _other, token_other = create_user_with_token(
        db_session_factory,
        email="plans_get_other@example.com",
        username="plans_get_other",
    )

    plan = create_plan_via_api(client, token_owner)

    own_response = client.get(f"/plans/{plan['id']}", headers=auth_headers(token_owner))
    assert own_response.status_code == 200, own_response.text
    assert own_response.json()["id"] == plan["id"]

    foreign_response = client.get(f"/plans/{plan['id']}", headers=auth_headers(token_other))
    assert foreign_response.status_code == 404, foreign_response.text


def test_delete_plan_owner_only(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, token_owner = create_user_with_token(
        db_session_factory,
        email="plans_del_owner@example.com",
        username="plans_del_owner",
    )
    _other, token_other = create_user_with_token(
        db_session_factory,
        email="plans_del_other@example.com",
        username="plans_del_other",
    )

    plan = create_plan_via_api(client, token_owner)

    foreign_delete = client.delete(f"/plans/{plan['id']}", headers=auth_headers(token_other))
    assert foreign_delete.status_code == 404, foreign_delete.text

    own_delete = client.delete(f"/plans/{plan['id']}", headers=auth_headers(token_owner))
    assert own_delete.status_code == 204, own_delete.text

    get_after_delete = client.get(f"/plans/{plan['id']}", headers=auth_headers(token_owner))
    assert get_after_delete.status_code == 404, get_after_delete.text


def test_bulk_delete_plans_one_success(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_bulk_delete_one@example.com",
        username="plans_bulk_delete_one",
    )
    plan = create_plan_via_api(client, token, title="Удалить один")

    response = client.post(
        "/plans/bulk-delete",
        headers=auth_headers(token),
        json={"plan_ids": [plan["id"]]},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"deleted_count": 1}

    get_after_delete = client.get(f"/plans/{plan['id']}", headers=auth_headers(token))
    assert get_after_delete.status_code == 404, get_after_delete.text


def test_bulk_delete_plans_multiple_success(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_bulk_delete_many@example.com",
        username="plans_bulk_delete_many",
    )
    first = create_plan_via_api(client, token, title="Удалить первый")
    second = create_plan_via_api(client, token, title="Удалить второй")
    keep = create_plan_via_api(client, token, title="Оставить")

    response = client.post(
        "/plans/bulk-delete",
        headers=auth_headers(token),
        json={"plan_ids": [first["id"], second["id"]]},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"deleted_count": 2}

    for plan in (first, second):
        deleted = client.get(f"/plans/{plan['id']}", headers=auth_headers(token))
        assert deleted.status_code == 404, deleted.text

    kept = client.get(f"/plans/{keep['id']}", headers=auth_headers(token))
    assert kept.status_code == 200, kept.text


def test_bulk_delete_plans_duplicate_ids_deduplicated(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_bulk_delete_duplicates@example.com",
        username="plans_bulk_delete_duplicates",
    )
    plan = create_plan_via_api(client, token, title="Дубликаты")

    response = client.post(
        "/plans/bulk-delete",
        headers=auth_headers(token),
        json={"plan_ids": [plan["id"], plan["id"], plan["id"]]},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"deleted_count": 1}

    deleted = client.get(f"/plans/{plan['id']}", headers=auth_headers(token))
    assert deleted.status_code == 404, deleted.text


def test_bulk_delete_plans_empty_ids_returns_422(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_bulk_delete_empty@example.com",
        username="plans_bulk_delete_empty",
    )

    response = client.post(
        "/plans/bulk-delete",
        headers=auth_headers(token),
        json={"plan_ids": []},
    )
    assert response.status_code == 422, response.text


def test_bulk_delete_plans_foreign_id_returns_404_without_partial_delete(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, owner_token = create_user_with_token(
        db_session_factory,
        email="plans_bulk_delete_owner_only@example.com",
        username="plans_bulk_delete_owner_only",
    )
    _other, other_token = create_user_with_token(
        db_session_factory,
        email="plans_bulk_delete_other@example.com",
        username="plans_bulk_delete_other",
    )

    own_plan = create_plan_via_api(client, owner_token, title="План владельца")
    foreign_plan = create_plan_via_api(client, other_token, title="Чужой план")

    response = client.post(
        "/plans/bulk-delete",
        headers=auth_headers(owner_token),
        json={"plan_ids": [own_plan["id"], foreign_plan["id"]]},
    )
    assert response.status_code == 404, response.text

    own_plan_still_exists = client.get(f"/plans/{own_plan['id']}", headers=auth_headers(owner_token))
    assert own_plan_still_exists.status_code == 200, own_plan_still_exists.text


def test_bulk_delete_plans_nonexistent_id_returns_404_without_partial_delete(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_bulk_delete_nonexistent@example.com",
        username="plans_bulk_delete_nonexistent",
    )
    own_plan = create_plan_via_api(client, token, title="План существует")

    response = client.post(
        "/plans/bulk-delete",
        headers=auth_headers(token),
        json={"plan_ids": [own_plan["id"], own_plan["id"] + 100000]},
    )
    assert response.status_code == 404, response.text

    own_plan_still_exists = client.get(f"/plans/{own_plan['id']}", headers=auth_headers(token))
    assert own_plan_still_exists.status_code == 200, own_plan_still_exists.text


def test_bulk_delete_plans_removes_slots_by_cascade(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_bulk_delete_slots_cascade@example.com",
        username="plans_bulk_delete_slots_cascade",
    )
    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=2, meals_per_day=3, title="Каскад")
    slot_ids = [slot["id"] for slot in plan["slots"]]
    assert len(slot_ids) == 6

    response = client.post(
        "/plans/bulk-delete",
        headers=auth_headers(token),
        json={"plan_ids": [plan["id"]]},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"deleted_count": 1}

    with db_session_factory() as db:
        orphan_slots = db.execute(select(PlanSlot).where(PlanSlot.id.in_(slot_ids))).scalars().all()
    assert orphan_slots == []


def test_delete_plan_keeps_shopping_list_document_and_drops_source_row(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_delete_keeps_shopping_doc@example.com",
        username="plans_delete_keeps_shopping_doc",
    )

    plan = create_plan_via_api(client, token, start_date="2026-03-24", days_count=1, meals_per_day=2, title="План для списка")
    shopping_list = create_shopping_list_from_plan_via_api(client, token, plan_id=plan["id"], title="Связанный список")
    assert len(shopping_list["sources"]) == 1
    source_id = shopping_list["sources"][0]["id"]

    delete_response = client.delete(f"/plans/{plan['id']}", headers=auth_headers(token))
    assert delete_response.status_code == 204, delete_response.text

    plan_get_after_delete = client.get(f"/plans/{plan['id']}", headers=auth_headers(token))
    assert plan_get_after_delete.status_code == 404, plan_get_after_delete.text

    shopping_list_after = client.get(f"/shopping-lists/{shopping_list['id']}", headers=auth_headers(token))
    assert shopping_list_after.status_code == 200, shopping_list_after.text
    assert shopping_list_after.json()["id"] == shopping_list["id"]
    assert shopping_list_after.json()["sources"] == []

    with db_session_factory() as db:
        source_rows = db.execute(select(ShoppingListSource).where(ShoppingListSource.id == source_id)).scalars().all()
    assert source_rows == []


def test_patch_plan_slot_updates_recipe_multiplier_and_pinned(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, token_owner = create_user_with_token(
        db_session_factory,
        email="plans_patch_owner@example.com",
        username="plans_patch_owner",
    )

    plan = create_plan_via_api(client, token_owner, days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]

    recipe = create_recipe_via_api(client, token_owner, name="Owner recipe")

    set_recipe_response = client.patch(
        f"/plans/{plan['id']}/slots/{slot_id}",
        headers=auth_headers(token_owner),
        json={"recipe_id": recipe["id"]},
    )
    assert set_recipe_response.status_code == 200, set_recipe_response.text
    assert set_recipe_response.json()["recipe_id"] == recipe["id"]

    set_multiplier_response = client.patch(
        f"/plans/{plan['id']}/slots/{slot_id}",
        headers=auth_headers(token_owner),
        json={"servings_multiplier": "1.75"},
    )
    assert set_multiplier_response.status_code == 200, set_multiplier_response.text
    assert Decimal(str(set_multiplier_response.json()["servings_multiplier"])) == Decimal("1.75")

    set_pinned_response = client.patch(
        f"/plans/{plan['id']}/slots/{slot_id}",
        headers=auth_headers(token_owner),
        json={"pinned": True},
    )
    assert set_pinned_response.status_code == 200, set_pinned_response.text
    assert set_pinned_response.json()["pinned"] is True

    clear_recipe_response = client.patch(
        f"/plans/{plan['id']}/slots/{slot_id}",
        headers=auth_headers(token_owner),
        json={"recipe_id": None},
    )
    assert clear_recipe_response.status_code == 200, clear_recipe_response.text
    assert clear_recipe_response.json()["recipe_id"] is None


def test_patch_plan_slot_disallows_foreign_private_recipe(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, token_owner = create_user_with_token(
        db_session_factory,
        email="plans_foreign_owner@example.com",
        username="plans_foreign_owner",
    )
    _other, token_other = create_user_with_token(
        db_session_factory,
        email="plans_foreign_other@example.com",
        username="plans_foreign_other",
    )

    foreign_private_recipe = create_recipe_via_api(client, token_other, name="Foreign private recipe")
    plan = create_plan_via_api(client, token_owner, days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]

    response = client.patch(
        f"/plans/{plan['id']}/slots/{slot_id}",
        headers=auth_headers(token_owner),
        json={"recipe_id": foreign_private_recipe["id"]},
    )
    assert response.status_code == 404, response.text


def test_patch_plan_slot_allows_foreign_published_recipe(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, token_owner = create_user_with_token(
        db_session_factory,
        email="plans_pub_owner@example.com",
        username="plans_pub_owner",
    )
    _other, token_other = create_user_with_token(
        db_session_factory,
        email="plans_pub_other@example.com",
        username="plans_pub_other",
    )

    foreign_recipe = create_recipe_via_api(client, token_other, name="Foreign publishable recipe")
    published_recipe = publish_recipe_via_api(client, token_other, foreign_recipe["id"])

    plan = create_plan_via_api(client, token_owner, days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]

    response = client.patch(
        f"/plans/{plan['id']}/slots/{slot_id}",
        headers=auth_headers(token_owner),
        json={"recipe_id": published_recipe["id"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["recipe_id"] == published_recipe["id"]


def test_patch_plan_slot_foreign_plan_or_slot_returns_404(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _owner, token_owner = create_user_with_token(
        db_session_factory,
        email="plans_404_owner@example.com",
        username="plans_404_owner",
    )
    _other, token_other = create_user_with_token(
        db_session_factory,
        email="plans_404_other@example.com",
        username="plans_404_other",
    )

    owner_plan = create_plan_via_api(client, token_owner, days_count=1, meals_per_day=2)
    other_plan = create_plan_via_api(client, token_other, days_count=1, meals_per_day=2)
    other_slot_id = other_plan["slots"][0]["id"]

    foreign_plan_response = client.patch(
        f"/plans/{other_plan['id']}/slots/{other_slot_id}",
        headers=auth_headers(token_owner),
        json={"pinned": True},
    )
    assert foreign_plan_response.status_code == 404, foreign_plan_response.text

    foreign_slot_response = client.patch(
        f"/plans/{owner_plan['id']}/slots/{other_slot_id}",
        headers=auth_headers(token_owner),
        json={"pinned": True},
    )
    assert foreign_slot_response.status_code == 404, foreign_slot_response.text


def test_patch_plan_slot_servings_multiplier_validation(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, token = create_user_with_token(
        db_session_factory,
        email="plans_validation@example.com",
        username="plans_validation",
    )

    plan = create_plan_via_api(client, token, days_count=1, meals_per_day=2)
    slot_id = plan["slots"][0]["id"]

    zero_response = client.patch(
        f"/plans/{plan['id']}/slots/{slot_id}",
        headers=auth_headers(token),
        json={"servings_multiplier": "0"},
    )
    assert zero_response.status_code == 422, zero_response.text

    negative_response = client.patch(
        f"/plans/{plan['id']}/slots/{slot_id}",
        headers=auth_headers(token),
        json={"servings_multiplier": "-1"},
    )
    assert negative_response.status_code == 422, negative_response.text
