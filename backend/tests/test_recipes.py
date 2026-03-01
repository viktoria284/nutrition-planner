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
