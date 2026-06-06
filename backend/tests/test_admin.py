from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.admin_action import AdminAction
from app.models.enums import UserRole
from app.services.security import hash_password
from app.services.users import create_user
from app.services.users import set_user_admin_role
from test_foods import (
    auth_headers,
    create_admin_user,
    create_food_via_api,
    login_and_get_token,
    register_user,
)
from test_recipes import create_recipe_via_api


TEST_PASSWORD = "Passw0rd!"


def create_superadmin_user(db_session_factory: sessionmaker[Session], *, email: str = "superadmin@example.com") -> None:
    db_session = db_session_factory()
    try:
        create_user(
            db=db_session,
            email=email,
            username=email.split("@", maxsplit=1)[0].replace(".", "_"),
            display_name="Super Admin",
            hashed_password=hash_password(TEST_PASSWORD),
            role=UserRole.superadmin,
        )
    finally:
        db_session.close()


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
        params={"include_public": "true", "meal_type": "lunch", "limit": 200},
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
        params={"include_public": "true", "meal_type": "lunch", "limit": 200},
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


def test_admin_can_close_report_when_recipe_is_no_longer_public(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_user(client, email="missing_recipe_owner@example.com", username="missing_recipe_owner")
    register_user(client, email="missing_recipe_reporter@example.com", username="missing_recipe_reporter")
    create_admin_user(db_session_factory, email="missing_recipe_admin@example.com")

    owner_token = login_and_get_token(client, identifier="missing_recipe_owner@example.com")
    reporter_token = login_and_get_token(client, identifier="missing_recipe_reporter@example.com")
    admin_token = login_and_get_token(client, identifier="missing_recipe_admin@example.com")

    ingredient = create_food_via_api(client, owner_token, name="Рис для скрытого рецепта")
    recipe = create_recipe_via_api(
        client,
        owner_token,
        name="Рецепт, который скроют до закрытия жалобы",
        meal_types=["dinner"],
    )
    add_ingredient = client.post(
        f"/recipes/{recipe['id']}/ingredients",
        headers=auth_headers(owner_token),
        json={"food_id": ingredient["id"], "grams": "100"},
    )
    assert add_ingredient.status_code == 201, add_ingredient.text
    publish = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish.status_code == 200, publish.text

    report_response = client.post(
        f"/recipes/{recipe['id']}/report",
        headers=auth_headers(reporter_token),
        json={"reason": "Жалоба перед скрытием"},
    )
    assert report_response.status_code == 200, report_response.text

    hide_response = client.post(
        f"/admin/recipes/{recipe['id']}/moderate",
        headers=auth_headers(admin_token),
        json={"action": "hide"},
    )
    assert hide_response.status_code == 200, hide_response.text
    assert hide_response.json()["is_listed"] is False

    unavailable_for_reporter = client.get(f"/recipes/{recipe['id']}", headers=auth_headers(reporter_token))
    assert unavailable_for_reporter.status_code == 404, unavailable_for_reporter.text

    reports_response = client.get("/admin/reports", headers=auth_headers(admin_token), params={"target_type": "recipe", "only_open": True})
    assert reports_response.status_code == 200, reports_response.text
    report = next(item for item in reports_response.json() if item["target_id"] == recipe["id"])

    resolve_response = client.post(
        f"/admin/reports/recipes/{report['id']}/resolve",
        headers=auth_headers(admin_token),
        json={"resolution": "no_action", "comment": "Объект уже недоступен"},
    )
    assert resolve_response.status_code == 200, resolve_response.text
    resolved = resolve_response.json()
    assert resolved["resolved_at"] is not None
    assert resolved["resolution"] == "no_action"


def test_admin_create_update_delete_public_recipe_and_food_updates_summary(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_user(client, email="admin_crud_user@example.com", username="admin_crud_user")
    create_admin_user(db_session_factory, email="admin_crud_admin@example.com")

    user_token = login_and_get_token(client, identifier="admin_crud_user@example.com")
    admin_token = login_and_get_token(client, identifier="admin_crud_admin@example.com")

    recipe_payload = {
        "name": "Системный завтрак",
        "description": "Публичный рецепт от редакции",
        "instructions": "Смешать и подать.",
        "servings_count": 2,
        "meal_types": ["breakfast"],
        "cook_time_minutes": 15,
    }
    forbidden_recipe = client.post("/admin/recipes", headers=auth_headers(user_token), json=recipe_payload)
    assert forbidden_recipe.status_code == 403, forbidden_recipe.text

    summary_before = client.get("/admin/summary", headers=auth_headers(admin_token))
    assert summary_before.status_code == 200, summary_before.text
    public_recipes_before = summary_before.json()["public_recipes"]

    created_recipe = client.post("/admin/recipes", headers=auth_headers(admin_token), json=recipe_payload)
    assert created_recipe.status_code == 201, created_recipe.text
    recipe = created_recipe.json()
    assert recipe["owner_user_id"] is None
    assert recipe["author_username"] == "Nutrition Planner"
    assert recipe["source"] == "community"
    assert recipe["status"] == "approved"
    assert recipe["is_listed"] is True

    public_catalog = client.get(
        "/recipes",
        headers=auth_headers(user_token),
        params={"include_public": "true", "limit": 200},
    )
    assert public_catalog.status_code == 200, public_catalog.text
    public_recipe = next(item for item in public_catalog.json() if item["id"] == recipe["id"])
    assert public_recipe["author_username"] == "Nutrition Planner"
    assert public_recipe["author_username"] != "demo_recipes"

    user_private_recipe = create_recipe_via_api(client, user_token, name="Личный черновик пользователя")
    user_public_recipe = create_recipe_via_api(client, user_token, name="Публичный рецепт пользователя")
    publish_user_recipe = client.post(f"/recipes/{user_public_recipe['id']}/publish", headers=auth_headers(user_token))
    assert publish_user_recipe.status_code == 200, publish_user_recipe.text

    system_recipes = client.get("/admin/recipes", headers=auth_headers(admin_token), params={"origin": "system", "limit": 200})
    assert system_recipes.status_code == 200, system_recipes.text
    system_recipe_ids = {item["id"] for item in system_recipes.json()}
    assert recipe["id"] in system_recipe_ids
    assert user_public_recipe["id"] not in system_recipe_ids

    user_recipes = client.get("/admin/recipes", headers=auth_headers(admin_token), params={"origin": "user", "limit": 200})
    assert user_recipes.status_code == 200, user_recipes.text
    user_recipe_ids = {item["id"] for item in user_recipes.json()}
    assert user_public_recipe["id"] in user_recipe_ids
    assert recipe["id"] not in user_recipe_ids
    assert user_private_recipe["id"] not in user_recipe_ids

    updated_recipe = client.patch(
        f"/admin/recipes/{recipe['id']}",
        headers=auth_headers(admin_token),
        json={"name": "Системный завтрак обновлён"},
    )
    assert updated_recipe.status_code == 200, updated_recipe.text
    assert updated_recipe.json()["name"] == "Системный завтрак обновлён"

    user_cannot_patch_recipe = client.patch(
        f"/recipes/{recipe['id']}",
        headers=auth_headers(user_token),
        json={"name": "Попытка правки чужого системного рецепта"},
    )
    assert user_cannot_patch_recipe.status_code == 404, user_cannot_patch_recipe.text

    summary_after_recipe = client.get("/admin/summary", headers=auth_headers(admin_token))
    assert summary_after_recipe.status_code == 200, summary_after_recipe.text
    assert summary_after_recipe.json()["public_recipes"] == public_recipes_before + 2

    food_payload = {
        "name": "Системная крупа",
        "brand": "Nutrition Planner",
        "category": "grains_bakery",
        "kcal": "330.00",
        "protein": "12.00",
        "fat": "3.00",
        "carbs": "68.00",
        "fiber": "7.00",
    }
    forbidden_food = client.post("/admin/foods", headers=auth_headers(user_token), json=food_payload)
    assert forbidden_food.status_code == 403, forbidden_food.text

    summary_before_food = client.get("/admin/summary", headers=auth_headers(admin_token))
    assert summary_before_food.status_code == 200, summary_before_food.text
    public_foods_before = summary_before_food.json()["public_foods"]

    created_food = client.post("/admin/foods", headers=auth_headers(admin_token), json=food_payload)
    assert created_food.status_code == 201, created_food.text
    food = created_food.json()
    assert food["owner_user_id"] is None
    assert food["source"] == "verified"
    assert food["status"] == "approved"
    assert food["is_listed"] is True

    user_private_food = create_food_via_api(client, user_token, name="Личный продукт пользователя")
    user_public_food = create_food_via_api(client, user_token, name="Публичный продукт пользователя")
    publish_user_food = client.post(f"/foods/{user_public_food['id']}/publish", headers=auth_headers(user_token))
    assert publish_user_food.status_code == 200, publish_user_food.text

    system_foods = client.get("/admin/foods", headers=auth_headers(admin_token), params={"origin": "system", "limit": 200})
    assert system_foods.status_code == 200, system_foods.text
    system_food_ids = {item["id"] for item in system_foods.json()}
    assert food["id"] in system_food_ids
    assert user_public_food["id"] not in system_food_ids

    user_foods = client.get("/admin/foods", headers=auth_headers(admin_token), params={"origin": "user", "limit": 200})
    assert user_foods.status_code == 200, user_foods.text
    user_food_ids = {item["id"] for item in user_foods.json()}
    assert user_public_food["id"] in user_food_ids
    assert food["id"] not in user_food_ids
    assert user_private_food["id"] not in user_food_ids

    updated_food = client.patch(
        f"/admin/foods/{food['id']}",
        headers=auth_headers(admin_token),
        json={"name": "Системная крупа обновлена"},
    )
    assert updated_food.status_code == 200, updated_food.text
    assert updated_food.json()["name"] == "Системная крупа обновлена"

    add_recipe_ingredient = client.post(
        f"/admin/recipes/{recipe['id']}/ingredients",
        headers=auth_headers(admin_token),
        json={"food_id": food["id"], "grams": "120"},
    )
    assert add_recipe_ingredient.status_code == 201, add_recipe_ingredient.text
    ingredient = add_recipe_ingredient.json()
    assert ingredient["food_id"] == food["id"]

    update_recipe_ingredient = client.patch(
        f"/admin/recipes/{recipe['id']}/ingredients/{ingredient['id']}",
        headers=auth_headers(admin_token),
        json={"grams": "150"},
    )
    assert update_recipe_ingredient.status_code == 200, update_recipe_ingredient.text
    assert update_recipe_ingredient.json()["grams"] in {"150.00", "150"}

    replace_steps = client.put(
        f"/admin/recipes/{recipe['id']}/steps",
        headers=auth_headers(admin_token),
        json={
            "steps": [
                {"position": 1, "text": "Промыть крупу.", "note": "Используйте холодную воду."},
                {"position": 2, "text": "Сварить до готовности.", "note": None},
            ]
        },
    )
    assert replace_steps.status_code == 200, replace_steps.text
    steps = replace_steps.json()
    assert [step["text"] for step in steps] == ["Промыть крупу.", "Сварить до готовности."]

    admin_recipe_detail = client.get(f"/admin/recipes/{recipe['id']}", headers=auth_headers(admin_token))
    assert admin_recipe_detail.status_code == 200, admin_recipe_detail.text
    recipe_detail = admin_recipe_detail.json()
    assert recipe_detail["ingredients"][0]["food"]["name"] == "Системная крупа обновлена"
    assert len(recipe_detail["steps"]) == 2
    assert recipe_detail["image_url"] is None

    summary_after_food = client.get("/admin/summary", headers=auth_headers(admin_token))
    assert summary_after_food.status_code == 200, summary_after_food.text
    assert summary_after_food.json()["public_foods"] == public_foods_before + 2

    delete_recipe = client.delete(f"/admin/recipes/{recipe['id']}", headers=auth_headers(admin_token))
    assert delete_recipe.status_code == 204, delete_recipe.text
    delete_food = client.delete(f"/admin/foods/{food['id']}", headers=auth_headers(admin_token))
    assert delete_food.status_code == 204, delete_food.text


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


def test_superadmin_can_manage_admin_roles_and_regular_admin_cannot(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    target = register_user(client, email="role_target@example.com", username="role_target")
    create_admin_user(db_session_factory, email="role_admin@example.com")
    create_superadmin_user(db_session_factory, email="role_super@example.com")

    user_token = login_and_get_token(client, identifier="role_target@example.com")
    admin_token = login_and_get_token(client, identifier="role_admin@example.com")
    super_token = login_and_get_token(client, identifier="role_super@example.com")

    user_forbidden = client.patch(
        f"/admin/users/{target['id']}/role",
        headers=auth_headers(user_token),
        json={"role": "admin"},
    )
    assert user_forbidden.status_code == 403, user_forbidden.text

    admin_forbidden = client.patch(
        f"/admin/users/{target['id']}/role",
        headers=auth_headers(admin_token),
        json={"role": "admin"},
    )
    assert admin_forbidden.status_code == 403, admin_forbidden.text

    promote = client.patch(
        f"/admin/users/{target['id']}/role",
        headers=auth_headers(super_token),
        json={"role": "admin"},
    )
    assert promote.status_code == 200, promote.text
    assert promote.json()["role"] == "admin"

    demote = client.patch(
        f"/admin/users/{target['id']}/role",
        headers=auth_headers(super_token),
        json={"role": "user"},
    )
    assert demote.status_code == 200, demote.text
    assert demote.json()["role"] == "user"

    db = db_session_factory()
    try:
        actions = (
            db.execute(select(AdminAction).where(AdminAction.target_user_id == target["id"]).order_by(AdminAction.id))
            .scalars()
            .all()
        )
        assert [action.details["to"] for action in actions] == ["admin", "user"]
    finally:
        db.close()


def test_cannot_demote_last_superadmin(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    create_superadmin_user(db_session_factory, email="last_super@example.com")
    super_token = login_and_get_token(client, identifier="last_super@example.com")

    me = client.get("/auth/me", headers=auth_headers(super_token))
    assert me.status_code == 200, me.text
    superadmin_id = me.json()["id"]

    response = client.patch(
        f"/admin/users/{superadmin_id}/role",
        headers=auth_headers(super_token),
        json={"role": "admin"},
    )
    assert response.status_code == 409, response.text
