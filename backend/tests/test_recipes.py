from decimal import Decimal

from fastapi.testclient import TestClient

TEST_PASSWORD = "Passw0rd!"


def register_user(
    client: TestClient,
    *,
    email: str,
    username: str,
    password: str = TEST_PASSWORD,
    display_name: str = "User",
) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "username": username,
            "password": password,
            "display_name": display_name,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def login_and_get_token(client: TestClient, *, identifier: str, password: str = TEST_PASSWORD) -> str:
    response = client.post(
        "/auth/login",
        data={"grant_type": "password", "username": identifier, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_food_via_api(
    client: TestClient,
    token: str,
    *,
    name: str,
    kcal: str,
    protein: str,
    fat: str,
    carbs: str,
    brand: str | None = None,
) -> dict:
    response = client.post(
        "/foods",
        headers=auth_headers(token),
        json={
            "name": name,
            "brand": brand,
            "kcal": kcal,
            "protein": protein,
            "fat": fat,
            "carbs": carbs,
        },
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
    description: str | None = None,
) -> dict:
    response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json={
            "name": name,
            "description": description,
            "servings_count": servings_count,
            "meal_types": meal_types or ["breakfast"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_recipe_ok_without_ingredients(client: TestClient) -> None:
    user = register_user(client, email="user1@example.com", username="userone")
    token = login_and_get_token(client, identifier="user1@example.com")

    create_response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json={
            "name": "Омлет",
            "description": "Быстрый завтрак",
            "servings_count": 2,
            "meal_types": ["breakfast"],
        },
    )
    assert create_response.status_code == 201, create_response.text
    recipe = create_response.json()
    assert recipe["owner_user_id"] == user["id"]
    assert recipe["name"] == "Омлет"
    assert Decimal(str(recipe["total_grams"])) == Decimal("0.00")
    assert Decimal(str(recipe["total_kcal"])) == Decimal("0.00")
    assert Decimal(str(recipe["per_serving_kcal"])) == Decimal("0.00")

    list_response = client.get("/recipes", headers=auth_headers(token))
    assert list_response.status_code == 200, list_response.text
    assert any(item["id"] == recipe["id"] for item in list_response.json())


def test_owner_only_get_recipe(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token_user1 = login_and_get_token(client, identifier="user1@example.com")

    create_response = client.post(
        "/recipes",
        headers=auth_headers(token_user1),
        json={
            "name": "Каша",
            "description": None,
            "servings_count": 1,
            "meal_types": ["breakfast"],
        },
    )
    assert create_response.status_code == 201, create_response.text
    recipe_id = create_response.json()["id"]

    register_user(client, email="user2@example.com", username="usertwo")
    token_user2 = login_and_get_token(client, identifier="user2@example.com")

    foreign_get = client.get(f"/recipes/{recipe_id}", headers=auth_headers(token_user2))
    assert foreign_get.status_code == 404, foreign_get.text


def test_validation_servings_count(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token = login_and_get_token(client, identifier="user1@example.com")

    response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json={
            "name": "Суп",
            "description": None,
            "servings_count": 0,
            "meal_types": ["lunch"],
        },
    )
    assert response.status_code == 422, response.text
    assert any(err["loc"][-1] == "servings_count" for err in response.json().get("detail", []))


def test_validation_meal_types_invalid_value(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token = login_and_get_token(client, identifier="user1@example.com")

    response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json={
            "name": "Паста",
            "description": None,
            "servings_count": 2,
            "meal_types": ["brunch"],
        },
    )
    assert response.status_code == 422, response.text
    assert any(err["loc"][-1] == "meal_types" for err in response.json().get("detail", []))


def test_validation_meal_types_empty(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token = login_and_get_token(client, identifier="user1@example.com")

    response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json={
            "name": "Салат",
            "description": None,
            "servings_count": 2,
            "meal_types": [],
        },
    )
    assert response.status_code == 422, response.text
    assert any(err["loc"][-1] == "meal_types" for err in response.json().get("detail", []))


def test_recipe_nutrients_calc_two_ingredients(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token = login_and_get_token(client, identifier="user1@example.com")

    food_a = create_food_via_api(
        client,
        token,
        name="Food A",
        kcal="100.00",
        protein="10.00",
        fat="0.00",
        carbs="10.00",
    )
    food_b = create_food_via_api(
        client,
        token,
        name="Food B",
        kcal="200.00",
        protein="0.00",
        fat="10.00",
        carbs="20.00",
    )

    create_recipe_response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json={
            "name": "Тестовый рецепт",
            "servings_count": 2,
            "meal_types": ["breakfast"],
        },
    )
    assert create_recipe_response.status_code == 201, create_recipe_response.text
    recipe_id = create_recipe_response.json()["id"]

    add_first = client.post(
        f"/recipes/{recipe_id}/ingredients",
        headers=auth_headers(token),
        json={"food_id": food_a["id"], "grams": "150"},
    )
    assert add_first.status_code == 201, add_first.text

    add_second = client.post(
        f"/recipes/{recipe_id}/ingredients",
        headers=auth_headers(token),
        json={"food_id": food_b["id"], "grams": "50"},
    )
    assert add_second.status_code == 201, add_second.text

    get_recipe_response = client.get(f"/recipes/{recipe_id}", headers=auth_headers(token))
    assert get_recipe_response.status_code == 200, get_recipe_response.text
    data = get_recipe_response.json()
    ingredients = data.get("ingredients") or []
    assert len(ingredients) == 2
    assert {item["food_id"] for item in ingredients} == {food_a["id"], food_b["id"]}

    assert Decimal(str(data["total_grams"])) == Decimal("200.00")
    assert Decimal(str(data["total_kcal"])) == Decimal("250.00")
    assert Decimal(str(data["total_protein"])) == Decimal("15.00")
    assert Decimal(str(data["total_fat"])) == Decimal("5.00")
    assert Decimal(str(data["total_carbs"])) == Decimal("25.00")
    assert Decimal(str(data["per_serving_kcal"])) == Decimal("125.00")
    assert Decimal(str(data["per_serving_protein"])) == Decimal("7.50")
    assert Decimal(str(data["per_serving_fat"])) == Decimal("2.50")
    assert Decimal(str(data["per_serving_carbs"])) == Decimal("12.50")


def test_ingredient_grams_must_be_positive(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token = login_and_get_token(client, identifier="user1@example.com")

    food = create_food_via_api(
        client,
        token,
        name="Food A",
        kcal="100.00",
        protein="10.00",
        fat="0.00",
        carbs="10.00",
    )
    create_recipe_response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json={
            "name": "Тестовый рецепт",
            "servings_count": 2,
            "meal_types": ["breakfast"],
        },
    )
    assert create_recipe_response.status_code == 201, create_recipe_response.text
    recipe_id = create_recipe_response.json()["id"]

    post_invalid = client.post(
        f"/recipes/{recipe_id}/ingredients",
        headers=auth_headers(token),
        json={"food_id": food["id"], "grams": "0"},
    )
    assert post_invalid.status_code == 422, post_invalid.text
    assert any(err["loc"][-1] == "grams" for err in post_invalid.json().get("detail", []))

    post_valid = client.post(
        f"/recipes/{recipe_id}/ingredients",
        headers=auth_headers(token),
        json={"food_id": food["id"], "grams": "10"},
    )
    assert post_valid.status_code == 201, post_valid.text
    ingredient_id = post_valid.json()["id"]

    patch_invalid = client.patch(
        f"/recipes/{recipe_id}/ingredients/{ingredient_id}",
        headers=auth_headers(token),
        json={"grams": "-1"},
    )
    assert patch_invalid.status_code == 422, patch_invalid.text
    assert any(err["loc"][-1] == "grams" for err in patch_invalid.json().get("detail", []))


def test_owner_only_ingredient_ops(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token_user1 = login_and_get_token(client, identifier="user1@example.com")

    register_user(client, email="user2@example.com", username="usertwo")
    token_user2 = login_and_get_token(client, identifier="user2@example.com")

    owner_food = create_food_via_api(
        client,
        token_user1,
        name="Owner Food",
        kcal="100.00",
        protein="10.00",
        fat="0.00",
        carbs="10.00",
    )
    foreign_food = create_food_via_api(
        client,
        token_user2,
        name="Foreign Food",
        kcal="90.00",
        protein="8.00",
        fat="1.00",
        carbs="12.00",
    )

    create_recipe_response = client.post(
        "/recipes",
        headers=auth_headers(token_user1),
        json={
            "name": "Owner recipe",
            "servings_count": 2,
            "meal_types": ["dinner"],
        },
    )
    assert create_recipe_response.status_code == 201, create_recipe_response.text
    recipe_id = create_recipe_response.json()["id"]

    add_owner_ing = client.post(
        f"/recipes/{recipe_id}/ingredients",
        headers=auth_headers(token_user1),
        json={"food_id": owner_food["id"], "grams": "100"},
    )
    assert add_owner_ing.status_code == 201, add_owner_ing.text
    ingredient_id = add_owner_ing.json()["id"]

    foreign_post = client.post(
        f"/recipes/{recipe_id}/ingredients",
        headers=auth_headers(token_user2),
        json={"food_id": foreign_food["id"], "grams": "25"},
    )
    assert foreign_post.status_code == 404, foreign_post.text

    foreign_patch = client.patch(
        f"/recipes/{recipe_id}/ingredients/{ingredient_id}",
        headers=auth_headers(token_user2),
        json={"grams": "30"},
    )
    assert foreign_patch.status_code == 404, foreign_patch.text

    foreign_delete = client.delete(
        f"/recipes/{recipe_id}/ingredients/{ingredient_id}",
        headers=auth_headers(token_user2),
    )
    assert foreign_delete.status_code == 404, foreign_delete.text


def test_publish_sets_approved_listed(client: TestClient) -> None:
    register_user(client, email="publisher@example.com", username="publisher")
    token = login_and_get_token(client, identifier="publisher@example.com")

    recipe = create_recipe_via_api(client, token, name="Recipe to publish")

    publish_response = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(token))
    assert publish_response.status_code == 200, publish_response.text
    published = publish_response.json()
    assert published["source"] == "community"
    assert published["status"] == "approved"
    assert published["is_listed"] is True

    second_publish = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(token))
    assert second_publish.status_code == 409, second_publish.text


def test_non_owner_can_get_only_published(client: TestClient) -> None:
    register_user(client, email="owner-visibility@example.com", username="ownervisibility")
    owner_token = login_and_get_token(client, identifier="owner-visibility@example.com")

    register_user(client, email="viewer-visibility@example.com", username="viewervisibility")
    viewer_token = login_and_get_token(client, identifier="viewer-visibility@example.com")

    private_recipe = create_recipe_via_api(client, owner_token, name="Private visibility recipe")

    private_get = client.get(f"/recipes/{private_recipe['id']}", headers=auth_headers(viewer_token))
    assert private_get.status_code == 404, private_get.text

    publish_response = client.post(f"/recipes/{private_recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    published_get = client.get(f"/recipes/{private_recipe['id']}", headers=auth_headers(viewer_token))
    assert published_get.status_code == 200, published_get.text


def test_self_report_400(client: TestClient) -> None:
    register_user(client, email="owner@example.com", username="owner")
    owner_token = login_and_get_token(client, identifier="owner@example.com")
    owner_recipe = create_recipe_via_api(client, owner_token, name="Owner recipe for report")

    publish_response = client.post(f"/recipes/{owner_recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    self_report = client.post(
        f"/recipes/{owner_recipe['id']}/report",
        headers=auth_headers(owner_token),
        json={"reason": "Спам"},
    )
    assert self_report.status_code == 400, self_report.text


def test_duplicate_report_409(client: TestClient) -> None:
    register_user(client, email="owner-duplicate@example.com", username="ownerduplicate")
    owner_token = login_and_get_token(client, identifier="owner-duplicate@example.com")
    owner_recipe = create_recipe_via_api(client, owner_token, name="Owner recipe duplicate report")

    publish_response = client.post(f"/recipes/{owner_recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    register_user(client, email="reporter@example.com", username="reporter")
    reporter_token = login_and_get_token(client, identifier="reporter@example.com")

    first_report = client.post(
        f"/recipes/{owner_recipe['id']}/report",
        headers=auth_headers(reporter_token),
        json={"reason": "Спам", "comment": "duplicate"},
    )
    assert first_report.status_code == 200, first_report.text
    assert first_report.json()["reports_count"] == 1

    duplicate_report = client.post(
        f"/recipes/{owner_recipe['id']}/report",
        headers=auth_headers(reporter_token),
        json={"reason": "Спам"},
    )
    assert duplicate_report.status_code == 409, duplicate_report.text


def test_report_requires_published(client: TestClient) -> None:
    register_user(client, email="owner-report-published@example.com", username="ownerreportpublished")
    owner_token = login_and_get_token(client, identifier="owner-report-published@example.com")
    private_recipe = create_recipe_via_api(client, owner_token, name="Private report target")

    register_user(client, email="viewer-report-published@example.com", username="viewerreportpublished")
    viewer_token = login_and_get_token(client, identifier="viewer-report-published@example.com")

    report_response = client.post(
        f"/recipes/{private_recipe['id']}/report",
        headers=auth_headers(viewer_token),
        json={"reason": "Спам"},
    )
    assert report_response.status_code == 404, report_response.text


def test_report_threshold_unlists_and_hides_from_others(client: TestClient) -> None:
    register_user(client, email="owner-threshold@example.com", username="ownerthreshold")
    owner_token = login_and_get_token(client, identifier="owner-threshold@example.com")
    recipe = create_recipe_via_api(client, owner_token, name="Threshold recipe")

    publish_response = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    report_users: list[str] = []
    for index in range(3):
        email = f"reporter{index}@example.com"
        username = f"reporter{index}"
        register_user(client, email=email, username=username)
        report_users.append(login_and_get_token(client, identifier=email))

    for token in report_users:
        report_response = client.post(
            f"/recipes/{recipe['id']}/report",
            headers=auth_headers(token),
            json={"reason": "Неверные данные"},
        )
        assert report_response.status_code == 200, report_response.text

    owner_get = client.get(f"/recipes/{recipe['id']}", headers=auth_headers(owner_token))
    assert owner_get.status_code == 200, owner_get.text
    data = owner_get.json()
    assert data["reports_count"] == 3
    assert data["status"] == "pending"
    assert data["is_listed"] is False

    viewer_get = client.get(f"/recipes/{recipe['id']}", headers=auth_headers(report_users[0]))
    assert viewer_get.status_code == 404, viewer_get.text


def test_withdraw_recipe_owner_only_and_unlist(client: TestClient) -> None:
    register_user(client, email="withdraw-owner@example.com", username="withdrawowner")
    owner_token = login_and_get_token(client, identifier="withdraw-owner@example.com")
    recipe = create_recipe_via_api(client, owner_token, name="Withdraw recipe")

    publish_response = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    register_user(client, email="withdraw-foreign@example.com", username="withdrawforeign")
    foreign_token = login_and_get_token(client, identifier="withdraw-foreign@example.com")

    foreign_withdraw = client.post(f"/recipes/{recipe['id']}/withdraw", headers=auth_headers(foreign_token))
    assert foreign_withdraw.status_code == 403, foreign_withdraw.text

    owner_withdraw = client.post(f"/recipes/{recipe['id']}/withdraw", headers=auth_headers(owner_token))
    assert owner_withdraw.status_code == 200, owner_withdraw.text
    assert owner_withdraw.json()["is_listed"] is False


def test_recipe_not_editable_after_publish(client: TestClient) -> None:
    register_user(client, email="edit-lock@example.com", username="editlock")
    token = login_and_get_token(client, identifier="edit-lock@example.com")
    recipe = create_recipe_via_api(client, token, name="Lock recipe")

    food = create_food_via_api(
        client,
        token,
        name="Ingredient Food",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="10.00",
    )

    publish_response = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(token))
    assert publish_response.status_code == 200, publish_response.text

    patch_response = client.patch(
        f"/recipes/{recipe['id']}",
        headers=auth_headers(token),
        json={"name": "Updated after publish"},
    )
    assert patch_response.status_code == 409, patch_response.text

    add_ingredient_response = client.post(
        f"/recipes/{recipe['id']}/ingredients",
        headers=auth_headers(token),
        json={"food_id": food["id"], "grams": "50"},
    )
    assert add_ingredient_response.status_code == 409, add_ingredient_response.text
