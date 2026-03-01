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
