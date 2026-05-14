from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.services.users import set_user_admin_role
from test_foods import (
    auth_headers,
    create_admin_user,
    create_food_via_api,
    login_and_get_token,
    register_user,
)
from test_recipes import create_recipe_via_api


def _create_profile(client: TestClient, token: str, *, name: str = "Профиль", kcal: float = 2000) -> dict:
    response = client.post(
        "/profiles",
        headers=auth_headers(token),
        json={
            "name": name,
            "target_kcal": kcal,
            "target_protein": 120,
            "target_fat": 70,
            "target_carbs": 220,
            "target_fiber": 25,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _autoplan_payload(profile_id: int) -> dict:
    return {
        "start_date": "2026-04-01",
        "days_count": 2,
        "meals_per_day": 2,
        "profile_id": profile_id,
        "use_public_recipes": True,
    }


def test_admin_summary_access_control(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    register_user(client, email="adminsum_user@example.com", username="adminsum_user")
    create_admin_user(db_session_factory, email="adminsum_admin@example.com")

    user_token = login_and_get_token(client, identifier="adminsum_user@example.com")
    admin_token = login_and_get_token(client, identifier="adminsum_admin@example.com")

    no_auth = client.get("/admin/summary")
    assert no_auth.status_code == 401, no_auth.text

    forbidden = client.get("/admin/summary", headers=auth_headers(user_token))
    assert forbidden.status_code == 403, forbidden.text

    ok = client.get("/admin/summary", headers=auth_headers(admin_token))
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert "total_users" in body
    assert "open_recipe_reports" in body


def test_admin_hide_restore_food_affects_public_search(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    register_user(client, email="food_owner@example.com", username="food_owner")
    register_user(client, email="food_reader@example.com", username="food_reader")
    create_admin_user(db_session_factory, email="food_admin@example.com")

    owner_token = login_and_get_token(client, identifier="food_owner@example.com")
    reader_token = login_and_get_token(client, identifier="food_reader@example.com")
    admin_token = login_and_get_token(client, identifier="food_admin@example.com")

    created_food = create_food_via_api(client, owner_token, name="Админ суп")
    food_id = created_food["id"]
    publish_response = client.post(f"/foods/{food_id}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    found_before = client.get("/foods/search", headers=auth_headers(reader_token), params={"q": "Админ"})
    assert found_before.status_code == 200, found_before.text
    assert any(item["id"] == food_id for item in found_before.json())

    hide_response = client.post(
        f"/admin/foods/{food_id}/moderate",
        headers=auth_headers(admin_token),
        json={"action": "hide"},
    )
    assert hide_response.status_code == 200, hide_response.text
    assert hide_response.json()["is_listed"] is False

    found_after_hide = client.get("/foods/search", headers=auth_headers(reader_token), params={"q": "Админ"})
    assert found_after_hide.status_code == 200, found_after_hide.text
    assert all(item["id"] != food_id for item in found_after_hide.json())

    forbidden_hide = client.post(
        f"/admin/foods/{food_id}/moderate",
        headers=auth_headers(reader_token),
        json={"action": "restore"},
    )
    assert forbidden_hide.status_code == 403, forbidden_hide.text

    restore_response = client.post(
        f"/admin/foods/{food_id}/moderate",
        headers=auth_headers(admin_token),
        json={"action": "restore"},
    )
    assert restore_response.status_code == 200, restore_response.text
    assert restore_response.json()["is_listed"] is True

    found_after_restore = client.get("/foods/search", headers=auth_headers(reader_token), params={"q": "Админ"})
    assert found_after_restore.status_code == 200, found_after_restore.text
    assert any(item["id"] == food_id for item in found_after_restore.json())


def test_admin_hide_restore_recipe_affects_public_and_autoplan(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    register_user(client, email="recipe_owner@example.com", username="recipe_owner")
    register_user(client, email="planner_user@example.com", username="planner_user")
    create_admin_user(db_session_factory, email="recipe_admin@example.com")

    owner_token = login_and_get_token(client, identifier="recipe_owner@example.com")
    planner_token = login_and_get_token(client, identifier="planner_user@example.com")
    admin_token = login_and_get_token(client, identifier="recipe_admin@example.com")

    owner_food = create_food_via_api(client, owner_token, name="Филе курицы")
    owner_food_id = owner_food["id"]

    lunch = create_recipe_via_api(
        client,
        owner_token,
        name="Публичный обед для модерации",
        meal_types=["lunch"],
        servings_count=1,
    )
    lunch_id = lunch["id"]
    add_lunch_ing = client.post(
        f"/recipes/{lunch_id}/ingredients",
        headers=auth_headers(owner_token),
        json={"food_id": owner_food_id, "grams": "120"},
    )
    assert add_lunch_ing.status_code == 201, add_lunch_ing.text
    publish_lunch = client.post(f"/recipes/{lunch_id}/publish", headers=auth_headers(owner_token))
    assert publish_lunch.status_code == 200, publish_lunch.text

    dinner = create_recipe_via_api(
        client,
        owner_token,
        name="Публичный ужин для модерации",
        meal_types=["dinner"],
        servings_count=1,
    )
    dinner_id = dinner["id"]
    add_dinner_ing = client.post(
        f"/recipes/{dinner_id}/ingredients",
        headers=auth_headers(owner_token),
        json={"food_id": owner_food_id, "grams": "140"},
    )
    assert add_dinner_ing.status_code == 201, add_dinner_ing.text
    publish_dinner = client.post(f"/recipes/{dinner_id}/publish", headers=auth_headers(owner_token))
    assert publish_dinner.status_code == 200, publish_dinner.text

    public_before = client.get(
        "/recipes",
        headers=auth_headers(planner_token),
        params={"include_public": "true", "meal_type": "lunch", "limit": 500},
    )
    assert public_before.status_code == 200, public_before.text
    assert any(item["id"] == lunch_id for item in public_before.json())

    hide_response = client.post(
        f"/admin/recipes/{lunch_id}/moderate",
        headers=auth_headers(admin_token),
        json={"action": "hide"},
    )
    assert hide_response.status_code == 200, hide_response.text
    assert hide_response.json()["is_listed"] is False

    public_after = client.get(
        "/recipes",
        headers=auth_headers(planner_token),
        params={"include_public": "true", "meal_type": "lunch", "limit": 500},
    )
    assert public_after.status_code == 200, public_after.text
    assert all(item["id"] != lunch_id for item in public_after.json())

    profile = _create_profile(client, planner_token, name="Autoplan Profile")
    autoplan_response = client.post(
        "/plans/autogenerate",
        headers=auth_headers(planner_token),
        json=_autoplan_payload(profile["id"]),
    )
    assert autoplan_response.status_code == 422, autoplan_response.text

    restore_response = client.post(
        f"/admin/recipes/{lunch_id}/moderate",
        headers=auth_headers(admin_token),
        json={"action": "restore"},
    )
    assert restore_response.status_code == 200, restore_response.text
    assert restore_response.json()["is_listed"] is True

    autoplan_ok = client.post(
        "/plans/autogenerate",
        headers=auth_headers(planner_token),
        json=_autoplan_payload(profile["id"]),
    )
    assert autoplan_ok.status_code == 201, autoplan_ok.text


def test_admin_reports_and_resolve_flow(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    register_user(client, email="report_owner@example.com", username="report_owner")
    register_user(client, email="reporter1@example.com", username="reporter1")
    create_admin_user(db_session_factory, email="report_admin@example.com")

    owner_token = login_and_get_token(client, identifier="report_owner@example.com")
    reporter_token = login_and_get_token(client, identifier="reporter1@example.com")
    admin_token = login_and_get_token(client, identifier="report_admin@example.com")

    created_food = create_food_via_api(client, owner_token, name="Продукт на жалобу")
    publish_food = client.post(f"/foods/{created_food['id']}/publish", headers=auth_headers(owner_token))
    assert publish_food.status_code == 200, publish_food.text

    report_food = client.post(
        f"/foods/{created_food['id']}/reports",
        headers=auth_headers(reporter_token),
        json={"reason": "Некорректные данные"},
    )
    assert report_food.status_code == 200, report_food.text

    created_recipe = create_recipe_via_api(
        client,
        owner_token,
        name="Рецепт на жалобу",
        meal_types=["dinner"],
    )
    add_ing = client.post(
        f"/recipes/{created_recipe['id']}/ingredients",
        headers=auth_headers(owner_token),
        json={"food_id": created_food["id"], "grams": "100"},
    )
    assert add_ing.status_code == 201, add_ing.text
    publish_recipe = client.post(f"/recipes/{created_recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_recipe.status_code == 200, publish_recipe.text

    report_recipe = client.post(
        f"/recipes/{created_recipe['id']}/report",
        headers=auth_headers(reporter_token),
        json={"reason": "Сомнительный рецепт", "comment": "Проверьте состав"},
    )
    assert report_recipe.status_code == 200, report_recipe.text

    list_reports = client.get("/admin/reports", headers=auth_headers(admin_token), params={"target_type": "all", "only_open": True})
    assert list_reports.status_code == 200, list_reports.text
    reports = list_reports.json()
    assert any(item["target_type"] == "food" for item in reports)
    assert any(item["target_type"] == "recipe" for item in reports)

    food_report = next(item for item in reports if item["target_type"] == "food")
    resolve_food = client.post(
        f"/admin/reports/foods/{food_report['id']}/resolve",
        headers=auth_headers(admin_token),
        json={"resolution": "content_hidden", "comment": "Скрыто администратором"},
    )
    assert resolve_food.status_code == 200, resolve_food.text
    resolved_food = resolve_food.json()
    assert resolved_food["resolved_at"] is not None
    assert resolved_food["resolution"] == "content_hidden"
    assert resolved_food["resolved_by_admin"] is not None

    food_detail = client.get(f"/foods/{created_food['id']}", headers=auth_headers(owner_token))
    assert food_detail.status_code == 200, food_detail.text
    assert food_detail.json()["is_listed"] is False

    recipe_report = next(item for item in reports if item["target_type"] == "recipe")
    resolve_recipe = client.post(
        f"/admin/reports/recipes/{recipe_report['id']}/resolve",
        headers=auth_headers(admin_token),
        json={"resolution": "no_action", "comment": "Нарушений не найдено"},
    )
    assert resolve_recipe.status_code == 200, resolve_recipe.text
    assert resolve_recipe.json()["resolved_at"] is not None

    open_after = client.get("/admin/reports", headers=auth_headers(admin_token), params={"target_type": "all", "only_open": True})
    assert open_after.status_code == 200, open_after.text
    assert len(open_after.json()) == 0


def test_admin_users_list_and_set_admin_role_service(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    created_user = register_user(client, email="users_list_member@example.com", username="users_list_member")
    create_admin_user(db_session_factory, email="users_list_admin@example.com")
    admin_token = login_and_get_token(client, identifier="users_list_admin@example.com")
    user_token = login_and_get_token(client, identifier="users_list_member@example.com")

    forbidden = client.get("/admin/users", headers=auth_headers(user_token))
    assert forbidden.status_code == 403, forbidden.text

    ok = client.get("/admin/users", headers=auth_headers(admin_token))
    assert ok.status_code == 200, ok.text
    users = ok.json()
    row = next(item for item in users if item["id"] == created_user["id"])
    assert row["email"] == "users_list_member@example.com"
    assert row["role"] == "user"

    db = db_session_factory()
    try:
        elevated = set_user_admin_role(db, email="users_list_member@example.com", is_admin=True)
        assert elevated is not None
        assert elevated.role.value == "admin"

        downgraded = set_user_admin_role(db, email="users_list_member@example.com", is_admin=False)
        assert downgraded is not None
        assert downgraded.role.value == "user"
    finally:
        db.close()
