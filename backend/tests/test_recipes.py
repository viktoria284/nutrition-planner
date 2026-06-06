from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

TEST_PASSWORD = "Passw0rd!"
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x90wS\xde"
    b"\x00\x00\x00\x0bIDATx\x9cc`\x00\x00\x00\x02\x00\x01"
    b"\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


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
    fiber: str | None = None,
    brand: str | None = None,
) -> dict:
    payload: dict[str, str | None] = {
        "name": name,
        "brand": brand,
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


def create_recipe_via_api(
    client: TestClient,
    token: str,
    *,
    name: str = "Тестовый рецепт",
    servings_count: int = 2,
    meal_types: list[str] | None = None,
    description: str | None = None,
    instructions: str | None = None,
    image_url: str | None = None,
    cook_time_minutes: int | None = None,
) -> dict:
    payload: dict[str, object] = {
        "name": name,
        "description": description,
        "servings_count": servings_count,
        "meal_types": meal_types or ["breakfast"],
    }
    if cook_time_minutes is not None:
        payload["cook_time_minutes"] = cook_time_minutes
    if instructions is not None:
        payload["instructions"] = instructions
    if image_url is not None:
        payload["image_url"] = image_url

    response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_serving_via_api(
    client: TestClient,
    token: str,
    *,
    food_id: int,
    name: str,
    grams: str,
) -> dict:
    response = client.post(
        f"/foods/{food_id}/servings",
        headers=auth_headers(token),
        json={
            "name": name,
            "grams": grams,
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
    assert recipe["cook_time_minutes"] is None

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


def test_create_recipe_with_cook_time_minutes(client: TestClient) -> None:
    register_user(client, email="cooktime-create@example.com", username="cooktimecreate")
    token = login_and_get_token(client, identifier="cooktime-create@example.com")

    recipe = create_recipe_via_api(
        client,
        token,
        name="Салат с курицей",
        meal_types=["lunch"],
        cook_time_minutes=25,
    )
    assert recipe["cook_time_minutes"] == 25


def test_patch_recipe_cook_time_minutes(client: TestClient) -> None:
    register_user(client, email="cooktime-patch@example.com", username="cooktimepatch")
    token = login_and_get_token(client, identifier="cooktime-patch@example.com")

    recipe = create_recipe_via_api(
        client,
        token,
        name="Тушеные овощи",
        meal_types=["dinner"],
    )

    response = client.patch(
        f"/recipes/{recipe['id']}",
        headers=auth_headers(token),
        json={"cook_time_minutes": 40},
    )
    assert response.status_code == 200, response.text
    assert response.json()["cook_time_minutes"] == 40


def test_recipe_cook_time_minutes_invalid_non_positive_returns_422(client: TestClient) -> None:
    register_user(client, email="cooktime-invalid@example.com", username="cooktimeinvalid")
    token = login_and_get_token(client, identifier="cooktime-invalid@example.com")

    response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json={
            "name": "Смузи",
            "servings_count": 1,
            "meal_types": ["snack"],
            "cook_time_minutes": 0,
        },
    )
    assert response.status_code == 422, response.text
    assert any(err["loc"][-1] == "cook_time_minutes" for err in response.json().get("detail", []))


def test_get_recipe_returns_cook_time_minutes(client: TestClient) -> None:
    register_user(client, email="cooktime-get@example.com", username="cooktimeget")
    token = login_and_get_token(client, identifier="cooktime-get@example.com")

    created = create_recipe_via_api(
        client,
        token,
        name="Паста с тунцом",
        meal_types=["dinner"],
        cook_time_minutes=30,
    )

    response = client.get(f"/recipes/{created['id']}", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    assert response.json()["cook_time_minutes"] == 30


def test_create_recipe_with_instructions(client: TestClient) -> None:
    register_user(client, email="instructions-create@example.com", username="instructionscreate")
    token = login_and_get_token(client, identifier="instructions-create@example.com")

    recipe = create_recipe_via_api(
        client,
        token,
        name="Паста с томатами",
        meal_types=["dinner"],
        instructions="1. Отварите пасту.\n2. Добавьте томаты.\n3. Перемешайте и подавайте.",
    )
    assert recipe["instructions"] is not None
    assert "Отварите пасту" in recipe["instructions"]


def test_patch_recipe_instructions(client: TestClient) -> None:
    register_user(client, email="instructions-patch@example.com", username="instructionspatch")
    token = login_and_get_token(client, identifier="instructions-patch@example.com")
    recipe = create_recipe_via_api(client, token, name="Салат", meal_types=["lunch"])

    response = client.patch(
        f"/recipes/{recipe['id']}",
        headers=auth_headers(token),
        json={"instructions": "1. Нарежьте овощи.\n2. Смешайте и подавайте."},
    )
    assert response.status_code == 200, response.text
    assert response.json()["instructions"] is not None
    assert "Нарежьте овощи" in response.json()["instructions"]


def test_blank_instructions_are_saved_as_null(client: TestClient) -> None:
    register_user(client, email="instructions-null@example.com", username="instructionsnull")
    token = login_and_get_token(client, identifier="instructions-null@example.com")

    created = create_recipe_via_api(
        client,
        token,
        name="Каша",
        meal_types=["breakfast"],
        instructions="   ",
    )
    assert created["instructions"] is None

    patched = client.patch(
        f"/recipes/{created['id']}",
        headers=auth_headers(token),
        json={"instructions": "  "},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["instructions"] is None


def test_get_recipe_returns_instructions(client: TestClient) -> None:
    register_user(client, email="instructions-get@example.com", username="instructionsget")
    token = login_and_get_token(client, identifier="instructions-get@example.com")

    created = create_recipe_via_api(
        client,
        token,
        name="Суп",
        meal_types=["lunch"],
        instructions="1. Смешайте ингредиенты.\n2. Варите 20 минут.",
    )

    response = client.get(f"/recipes/{created['id']}", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    assert response.json()["instructions"] is not None


def test_create_recipe_with_image_url(client: TestClient) -> None:
    register_user(client, email="image-create@example.com", username="imagecreate")
    token = login_and_get_token(client, identifier="image-create@example.com")

    recipe = create_recipe_via_api(
        client,
        token,
        name="Боул",
        meal_types=["lunch"],
        image_url="https://example.com/image.jpg",
    )
    assert recipe["image_url"] == "https://example.com/image.jpg"


def test_invalid_recipe_image_url_returns_422(client: TestClient) -> None:
    register_user(client, email="image-invalid@example.com", username="imageinvalid")
    token = login_and_get_token(client, identifier="image-invalid@example.com")

    response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json={
            "name": "Смузи",
            "servings_count": 1,
            "meal_types": ["snack"],
            "image_url": "ftp://bad-url.local",
        },
    )
    assert response.status_code == 422, response.text
    assert any(err["loc"][-1] == "image_url" for err in response.json().get("detail", []))


def test_blank_image_url_is_saved_as_null(client: TestClient) -> None:
    register_user(client, email="image-null@example.com", username="imagenull")
    token = login_and_get_token(client, identifier="image-null@example.com")

    created = create_recipe_via_api(
        client,
        token,
        name="Салат",
        meal_types=["lunch"],
        image_url="   ",
    )
    assert created["image_url"] is None

    patched = client.patch(
        f"/recipes/{created['id']}",
        headers=auth_headers(token),
        json={"image_url": "   "},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["image_url"] is None


def test_get_recipe_returns_image_url(client: TestClient) -> None:
    register_user(client, email="image-get@example.com", username="imageget")
    token = login_and_get_token(client, identifier="image-get@example.com")
    created = create_recipe_via_api(
        client,
        token,
        name="Запеканка",
        meal_types=["dinner"],
        image_url="https://images.example.org/casserole.png",
    )

    response = client.get(f"/recipes/{created['id']}", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    assert response.json()["image_url"] == "https://images.example.org/casserole.png"


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


def test_validation_meal_types_duplicate(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token = login_and_get_token(client, identifier="user1@example.com")

    response = client.post(
        "/recipes",
        headers=auth_headers(token),
        json={
            "name": "Смузи",
            "description": None,
            "servings_count": 1,
            "meal_types": ["breakfast", "breakfast"],
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
        fiber="6.00",
    )
    food_b = create_food_via_api(
        client,
        token,
        name="Food B",
        kcal="200.00",
        protein="0.00",
        fat="10.00",
        carbs="20.00",
        fiber="2.00",
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
    assert Decimal(str(data["total_fiber"])) == Decimal("10.00")
    assert Decimal(str(data["per_serving_kcal"])) == Decimal("125.00")
    assert Decimal(str(data["per_serving_protein"])) == Decimal("7.50")
    assert Decimal(str(data["per_serving_fat"])) == Decimal("2.50")
    assert Decimal(str(data["per_serving_carbs"])) == Decimal("12.50")
    assert Decimal(str(data["per_serving_fiber"])) == Decimal("5.00")


def test_recipe_fiber_updates_when_ingredients_change(client: TestClient) -> None:
    register_user(client, email="recipe-fiber-update@example.com", username="recipefiberupdate")
    token = login_and_get_token(client, identifier="recipe-fiber-update@example.com")

    food = create_food_via_api(
        client,
        token,
        name="Fiber Food",
        kcal="120.00",
        protein="5.00",
        fat="2.00",
        carbs="18.00",
        fiber="8.00",
    )
    recipe = create_recipe_via_api(client, token, servings_count=2)
    add = client.post(
        f"/recipes/{recipe['id']}/ingredients",
        headers=auth_headers(token),
        json={"food_id": food["id"], "grams": "100"},
    )
    assert add.status_code == 201, add.text
    ingredient_id = add.json()["id"]

    before = client.get(f"/recipes/{recipe['id']}", headers=auth_headers(token))
    assert before.status_code == 200, before.text
    assert Decimal(str(before.json()["per_serving_fiber"])) == Decimal("4.00")

    patch = client.patch(
        f"/recipes/{recipe['id']}/ingredients/{ingredient_id}",
        headers=auth_headers(token),
        json={"grams": "150"},
    )
    assert patch.status_code == 200, patch.text

    after = client.get(f"/recipes/{recipe['id']}", headers=auth_headers(token))
    assert after.status_code == 200, after.text
    assert Decimal(str(after.json()["per_serving_fiber"])) == Decimal("6.00")


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


def test_add_ingredient_by_serving_calc_grams_and_totals(client: TestClient) -> None:
    register_user(client, email="serving-user@example.com", username="servinguser")
    token = login_and_get_token(client, identifier="serving-user@example.com")

    food = create_food_via_api(
        client,
        token,
        name="Serving Food",
        kcal="100.00",
        protein="10.00",
        fat="0.00",
        carbs="10.00",
    )
    serving = create_serving_via_api(
        client,
        token,
        food_id=food["id"],
        name="1 шт",
        grams="120",
    )
    recipe = create_recipe_via_api(client, token, servings_count=2)

    add_response = client.post(
        f"/recipes/{recipe['id']}/ingredients",
        headers=auth_headers(token),
        json={
            "food_id": food["id"],
            "serving_id": serving["id"],
            "multiplier": "2",
        },
    )
    assert add_response.status_code == 201, add_response.text
    ingredient = add_response.json()
    assert Decimal(str(ingredient["grams"])) == Decimal("240.00")
    assert ingredient["serving_id"] == serving["id"]
    assert Decimal(str(ingredient["multiplier"])) == Decimal("2.00")

    get_recipe_response = client.get(f"/recipes/{recipe['id']}", headers=auth_headers(token))
    assert get_recipe_response.status_code == 200, get_recipe_response.text
    data = get_recipe_response.json()
    assert Decimal(str(data["total_grams"])) == Decimal("240.00")
    assert Decimal(str(data["total_kcal"])) == Decimal("240.00")
    assert Decimal(str(data["total_protein"])) == Decimal("24.00")
    assert Decimal(str(data["total_fat"])) == Decimal("0.00")
    assert Decimal(str(data["total_carbs"])) == Decimal("24.00")
    assert Decimal(str(data["total_fiber"])) == Decimal("0.00")
    assert Decimal(str(data["per_serving_kcal"])) == Decimal("120.00")
    assert Decimal(str(data["per_serving_protein"])) == Decimal("12.00")
    assert Decimal(str(data["per_serving_fat"])) == Decimal("0.00")
    assert Decimal(str(data["per_serving_carbs"])) == Decimal("12.00")
    assert Decimal(str(data["per_serving_fiber"])) == Decimal("0.00")


def test_serving_must_match_food(client: TestClient) -> None:
    register_user(client, email="serving-match@example.com", username="servingmatch")
    token = login_and_get_token(client, identifier="serving-match@example.com")

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
        kcal="90.00",
        protein="9.00",
        fat="1.00",
        carbs="8.00",
    )
    serving_b = create_serving_via_api(
        client,
        token,
        food_id=food_b["id"],
        name="1 ложка",
        grams="30",
    )
    recipe = create_recipe_via_api(client, token, servings_count=2)

    response = client.post(
        f"/recipes/{recipe['id']}/ingredients",
        headers=auth_headers(token),
        json={
            "food_id": food_a["id"],
            "serving_id": serving_b["id"],
            "multiplier": "1",
        },
    )
    assert response.status_code == 422, response.text


def test_update_ingredient_food_without_matching_serving_switches_to_grams(client: TestClient) -> None:
    register_user(client, email="serving-switch@example.com", username="servingswitch")
    token = login_and_get_token(client, identifier="serving-switch@example.com")

    food_with_serving = create_food_via_api(
        client,
        token,
        name="Food With Serving",
        kcal="100.00",
        protein="10.00",
        fat="0.00",
        carbs="10.00",
    )
    food_without_serving = create_food_via_api(
        client,
        token,
        name="Food Without Serving",
        kcal="90.00",
        protein="9.00",
        fat="1.00",
        carbs="8.00",
    )
    serving = create_serving_via_api(
        client,
        token,
        food_id=food_with_serving["id"],
        name="1 шт",
        grams="120",
    )
    recipe = create_recipe_via_api(client, token, servings_count=1)

    add_response = client.post(
        f"/recipes/{recipe['id']}/ingredients",
        headers=auth_headers(token),
        json={
            "food_id": food_with_serving["id"],
            "serving_id": serving["id"],
            "multiplier": "2",
        },
    )
    assert add_response.status_code == 201, add_response.text
    ingredient = add_response.json()

    patch_response = client.patch(
        f"/recipes/{recipe['id']}/ingredients/{ingredient['id']}",
        headers=auth_headers(token),
        json={"food_id": food_without_serving["id"]},
    )
    assert patch_response.status_code == 200, patch_response.text
    updated = patch_response.json()
    assert updated["food_id"] == food_without_serving["id"]
    assert Decimal(str(updated["grams"])) == Decimal("240.00")
    assert updated["serving_id"] is None
    assert updated["multiplier"] is None


def test_multiplier_positive(client: TestClient) -> None:
    register_user(client, email="serving-mult@example.com", username="servingmult")
    token = login_and_get_token(client, identifier="serving-mult@example.com")

    food = create_food_via_api(
        client,
        token,
        name="Food C",
        kcal="110.00",
        protein="11.00",
        fat="2.00",
        carbs="12.00",
    )
    serving = create_serving_via_api(
        client,
        token,
        food_id=food["id"],
        name="Порция",
        grams="100",
    )
    recipe = create_recipe_via_api(client, token, servings_count=1)

    response = client.post(
        f"/recipes/{recipe['id']}/ingredients",
        headers=auth_headers(token),
        json={
            "food_id": food["id"],
            "serving_id": serving["id"],
            "multiplier": "0",
        },
    )
    assert response.status_code == 422, response.text


def test_fractional_multiplier(client: TestClient) -> None:
    register_user(client, email="fractional-mult@example.com", username="fractionalmult")
    token = login_and_get_token(client, identifier="fractional-mult@example.com")

    food = create_food_via_api(
        client,
        token,
        name="Food Fractional Mult",
        kcal="100.00",
        protein="10.00",
        fat="0.00",
        carbs="10.00",
    )
    serving = create_serving_via_api(
        client,
        token,
        food_id=food["id"],
        name="1 шт",
        grams="120",
    )
    recipe = create_recipe_via_api(client, token, servings_count=2)

    add_response = client.post(
        f"/recipes/{recipe['id']}/ingredients",
        headers=auth_headers(token),
        json={
            "food_id": food["id"],
            "serving_id": serving["id"],
            "multiplier": "0.5",
        },
    )
    assert add_response.status_code == 201, add_response.text
    ingredient = add_response.json()
    assert Decimal(str(ingredient["grams"])) == Decimal("60.00")

    get_recipe_response = client.get(f"/recipes/{recipe['id']}", headers=auth_headers(token))
    assert get_recipe_response.status_code == 200, get_recipe_response.text
    data = get_recipe_response.json()
    assert Decimal(str(data["total_grams"])) == Decimal("60.00")
    assert Decimal(str(data["total_kcal"])) == Decimal("60.00")
    assert Decimal(str(data["per_serving_kcal"])) == Decimal("30.00")


def test_fractional_grams_with_rounding(client: TestClient) -> None:
    register_user(client, email="fractional-grams@example.com", username="fractionalgrams")
    token = login_and_get_token(client, identifier="fractional-grams@example.com")

    food = create_food_via_api(
        client,
        token,
        name="Food Fractional Grams",
        kcal="123.45",
        protein="7.89",
        fat="3.21",
        carbs="11.11",
    )
    recipe = create_recipe_via_api(client, token, servings_count=2)

    add_response = client.post(
        f"/recipes/{recipe['id']}/ingredients",
        headers=auth_headers(token),
        json={"food_id": food["id"], "grams": "12.5"},
    )
    assert add_response.status_code == 201, add_response.text
    ingredient = add_response.json()
    assert Decimal(str(ingredient["grams"])) == Decimal("12.50")

    get_recipe_response = client.get(f"/recipes/{recipe['id']}", headers=auth_headers(token))
    assert get_recipe_response.status_code == 200, get_recipe_response.text
    data = get_recipe_response.json()
    assert Decimal(str(data["total_grams"])) == Decimal("12.50")
    assert Decimal(str(data["total_kcal"])) == Decimal("15.43")
    assert Decimal(str(data["total_protein"])) == Decimal("0.99")
    assert Decimal(str(data["total_fat"])) == Decimal("0.40")
    assert Decimal(str(data["total_carbs"])) == Decimal("1.39")
    assert Decimal(str(data["total_fiber"])) == Decimal("0.00")
    assert Decimal(str(data["per_serving_kcal"])) == Decimal("7.72")
    assert Decimal(str(data["per_serving_protein"])) == Decimal("0.49")
    assert Decimal(str(data["per_serving_fat"])) == Decimal("0.20")
    assert Decimal(str(data["per_serving_carbs"])) == Decimal("0.69")
    assert Decimal(str(data["per_serving_fiber"])) == Decimal("0.00")


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


def test_owner_only_recipe_update_delete(client: TestClient) -> None:
    register_user(client, email="owner-recipe@example.com", username="ownerrecipe")
    owner_token = login_and_get_token(client, identifier="owner-recipe@example.com")
    recipe = create_recipe_via_api(client, owner_token, name="Owner only recipe")

    register_user(client, email="other-recipe@example.com", username="otherrecipe")
    other_token = login_and_get_token(client, identifier="other-recipe@example.com")

    foreign_patch = client.patch(
        f"/recipes/{recipe['id']}",
        headers=auth_headers(other_token),
        json={"name": "Hacked"},
    )
    assert foreign_patch.status_code == 404, foreign_patch.text

    foreign_delete = client.delete(
        f"/recipes/{recipe['id']}",
        headers=auth_headers(other_token),
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


def test_recipe_list_include_public_shows_approved_and_listed_public_recipes(
    client: TestClient,
) -> None:
    register_user(client, email="list-owner@example.com", username="listowner")
    owner_token = login_and_get_token(client, identifier="list-owner@example.com")
    register_user(client, email="list-viewer@example.com", username="listviewer")
    viewer_token = login_and_get_token(client, identifier="list-viewer@example.com")

    own_recipe = create_recipe_via_api(client, viewer_token, name="Viewer Own Recipe")
    _private_recipe = create_recipe_via_api(client, owner_token, name="Owner Private Recipe")
    public_recipe = create_recipe_via_api(client, owner_token, name="Owner Public Recipe")
    publish_response = client.post(
        f"/recipes/{public_recipe['id']}/publish",
        headers=auth_headers(owner_token),
    )
    assert publish_response.status_code == 200, publish_response.text

    default_list_response = client.get("/recipes", headers=auth_headers(viewer_token))
    assert default_list_response.status_code == 200, default_list_response.text
    default_ids = {item["id"] for item in default_list_response.json()}
    assert own_recipe["id"] in default_ids
    assert public_recipe["id"] not in default_ids

    include_public_response = client.get(
        "/recipes?include_public=true",
        headers=auth_headers(viewer_token),
    )
    assert include_public_response.status_code == 200, include_public_response.text
    include_public_ids = {item["id"] for item in include_public_response.json()}
    assert own_recipe["id"] in include_public_ids
    assert public_recipe["id"] in include_public_ids


def test_recipe_list_include_public_hides_foreign_private_recipes(
    client: TestClient,
) -> None:
    register_user(client, email="list-private-owner@example.com", username="listprivateowner")
    owner_token = login_and_get_token(client, identifier="list-private-owner@example.com")
    register_user(client, email="list-private-viewer@example.com", username="listprivateviewer")
    viewer_token = login_and_get_token(client, identifier="list-private-viewer@example.com")

    private_recipe = create_recipe_via_api(client, owner_token, name="Hidden Private Recipe")

    response = client.get(
        "/recipes?include_public=true",
        headers=auth_headers(viewer_token),
    )
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert private_recipe["id"] not in ids


def test_recipe_list_include_public_hides_withdrawn_recipes(
    client: TestClient,
) -> None:
    register_user(client, email="list-withdraw-owner@example.com", username="listwithdrawowner")
    owner_token = login_and_get_token(client, identifier="list-withdraw-owner@example.com")
    register_user(client, email="list-withdraw-viewer@example.com", username="listwithdrawviewer")
    viewer_token = login_and_get_token(client, identifier="list-withdraw-viewer@example.com")

    active_public_recipe = create_recipe_via_api(client, owner_token, name="Active Public Recipe")
    withdraw_recipe = create_recipe_via_api(client, owner_token, name="Withdrawn Public Recipe")

    active_publish_response = client.post(
        f"/recipes/{active_public_recipe['id']}/publish",
        headers=auth_headers(owner_token),
    )
    assert active_publish_response.status_code == 200, active_publish_response.text

    withdraw_publish_response = client.post(
        f"/recipes/{withdraw_recipe['id']}/publish",
        headers=auth_headers(owner_token),
    )
    assert withdraw_publish_response.status_code == 200, withdraw_publish_response.text
    withdraw_response = client.post(
        f"/recipes/{withdraw_recipe['id']}/withdraw",
        headers=auth_headers(owner_token),
    )
    assert withdraw_response.status_code == 200, withdraw_response.text

    response = client.get(
        "/recipes?include_public=true",
        headers=auth_headers(viewer_token),
    )
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert active_public_recipe["id"] in ids
    assert withdraw_recipe["id"] not in ids


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
    assert owner_withdraw.json()["source"] == "private"
    assert owner_withdraw.json()["status"] == "draft"
    assert owner_withdraw.json()["is_listed"] is False


def test_recipe_editable_after_withdraw(client: TestClient) -> None:
    register_user(client, email="withdraw-edit@example.com", username="withdrawedit")
    token = login_and_get_token(client, identifier="withdraw-edit@example.com")
    recipe = create_recipe_via_api(client, token, name="Editable after withdraw")
    food = create_food_via_api(
        client,
        token,
        name="Withdraw Editable Ingredient",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="10.00",
    )

    publish_response = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(token))
    assert publish_response.status_code == 200, publish_response.text

    withdraw_response = client.post(f"/recipes/{recipe['id']}/withdraw", headers=auth_headers(token))
    assert withdraw_response.status_code == 200, withdraw_response.text
    withdrawn = withdraw_response.json()
    assert withdrawn["source"] == "private"
    assert withdrawn["status"] == "draft"
    assert withdrawn["is_listed"] is False

    patch_response = client.patch(
        f"/recipes/{recipe['id']}",
        headers=auth_headers(token),
        json={"name": "Updated after withdraw"},
    )
    assert patch_response.status_code == 200, patch_response.text
    assert patch_response.json()["name"] == "Updated after withdraw"

    add_ingredient_response = client.post(
        f"/recipes/{recipe['id']}/ingredients",
        headers=auth_headers(token),
        json={"food_id": food["id"], "grams": "50"},
    )
    assert add_ingredient_response.status_code == 201, add_ingredient_response.text


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


def test_public_recipes_include_all_meal_types(client: TestClient) -> None:
    register_user(client, email="public-all-owner@example.com", username="publicallowner")
    owner_token = login_and_get_token(client, identifier="public-all-owner@example.com")
    register_user(client, email="public-all-viewer@example.com", username="publicallviewer")
    viewer_token = login_and_get_token(client, identifier="public-all-viewer@example.com")

    recipes = [
        create_recipe_via_api(client, owner_token, name="P breakfast", meal_types=["breakfast"]),
        create_recipe_via_api(client, owner_token, name="P lunch", meal_types=["lunch"]),
        create_recipe_via_api(client, owner_token, name="P dinner", meal_types=["dinner"]),
        create_recipe_via_api(client, owner_token, name="P snack", meal_types=["snack"]),
    ]
    for recipe in recipes:
        publish_response = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(owner_token))
        assert publish_response.status_code == 200, publish_response.text

    response = client.get("/recipes?include_public=true&limit=100", headers=auth_headers(viewer_token))
    assert response.status_code == 200, response.text
    meal_types = {item["meal_types"][0] for item in response.json() if item["name"].startswith("P ")}
    assert {"breakfast", "lunch", "dinner", "snack"}.issubset(meal_types)


def test_public_recipes_filter_by_breakfast(client: TestClient) -> None:
    register_user(client, email="public-breakfast-owner@example.com", username="publicbreakfastowner")
    owner_token = login_and_get_token(client, identifier="public-breakfast-owner@example.com")
    register_user(client, email="public-breakfast-viewer@example.com", username="publicbreakfastviewer")
    viewer_token = login_and_get_token(client, identifier="public-breakfast-viewer@example.com")

    breakfast = create_recipe_via_api(client, owner_token, name="Breakfast Only", meal_types=["breakfast"])
    lunch = create_recipe_via_api(client, owner_token, name="Lunch Only", meal_types=["lunch"])
    for recipe in (breakfast, lunch):
        publish_response = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(owner_token))
        assert publish_response.status_code == 200, publish_response.text

    response = client.get(
        "/recipes?include_public=true&meal_type=breakfast&limit=100",
        headers=auth_headers(viewer_token),
    )
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert breakfast["id"] in ids
    assert lunch["id"] not in ids


def test_public_recipes_filter_by_lunch(client: TestClient) -> None:
    register_user(client, email="public-lunch-owner@example.com", username="publiclunchowner")
    owner_token = login_and_get_token(client, identifier="public-lunch-owner@example.com")
    register_user(client, email="public-lunch-viewer@example.com", username="publiclunchviewer")
    viewer_token = login_and_get_token(client, identifier="public-lunch-viewer@example.com")

    breakfast = create_recipe_via_api(client, owner_token, name="B only", meal_types=["breakfast"])
    lunch = create_recipe_via_api(client, owner_token, name="L only", meal_types=["lunch"])
    for recipe in (breakfast, lunch):
        publish_response = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(owner_token))
        assert publish_response.status_code == 200, publish_response.text

    response = client.get("/recipes?include_public=true&meal_type=lunch&limit=100", headers=auth_headers(viewer_token))
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert lunch["id"] in ids
    assert breakfast["id"] not in ids


def test_recipe_payload_includes_author_fields(client: TestClient) -> None:
    register_user(client, email="author-fields-owner@example.com", username="authorfieldsowner")
    owner_token = login_and_get_token(client, identifier="author-fields-owner@example.com")
    recipe = create_recipe_via_api(client, owner_token, name="Author fields", meal_types=["dinner"])

    response = client.get(f"/recipes/{recipe['id']}", headers=auth_headers(owner_token))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["author_id"] == payload["owner_user_id"]
    assert payload["author_username"] == "authorfieldsowner"


def test_public_recipes_filter_by_author_id(client: TestClient) -> None:
    register_user(client, email="author-filter-owner1@example.com", username="authorfilterowner1")
    owner1_token = login_and_get_token(client, identifier="author-filter-owner1@example.com")
    register_user(client, email="author-filter-owner2@example.com", username="authorfilterowner2")
    owner2_token = login_and_get_token(client, identifier="author-filter-owner2@example.com")
    register_user(client, email="author-filter-viewer@example.com", username="authorfilterviewer")
    viewer_token = login_and_get_token(client, identifier="author-filter-viewer@example.com")

    owner1_recipe = create_recipe_via_api(client, owner1_token, name="Owner one public", meal_types=["lunch"])
    owner2_recipe = create_recipe_via_api(client, owner2_token, name="Owner two public", meal_types=["lunch"])
    for recipe in (owner1_recipe, owner2_recipe):
        token = owner1_token if recipe["id"] == owner1_recipe["id"] else owner2_token
        publish_response = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(token))
        assert publish_response.status_code == 200, publish_response.text

    response = client.get(
        f"/recipes?include_public=true&author_id={owner1_recipe['owner_user_id']}&limit=100",
        headers=auth_headers(viewer_token),
    )
    assert response.status_code == 200, response.text
    items = response.json()
    ids = {item["id"] for item in items}
    assert owner1_recipe["id"] in ids
    assert owner2_recipe["id"] not in ids
    assert all(item["author_username"] == "authorfilterowner1" for item in items)


def test_max_cook_time_filter_returns_only_recipes_up_to_max(client: TestClient) -> None:
    register_user(client, email="cook-filter-owner@example.com", username="cookfilterowner")
    token = login_and_get_token(client, identifier="cook-filter-owner@example.com")

    quick = create_recipe_via_api(client, token, name="Quick", cook_time_minutes=15, meal_types=["dinner"])
    long = create_recipe_via_api(client, token, name="Long", cook_time_minutes=45, meal_types=["dinner"])
    unknown = create_recipe_via_api(client, token, name="Unknown", meal_types=["dinner"])

    response = client.get("/recipes?max_cook_time_minutes=30&limit=100", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert quick["id"] in ids
    assert long["id"] not in ids
    assert unknown["id"] not in ids


def test_invalid_max_cook_time_filter_returns_422(client: TestClient) -> None:
    register_user(client, email="cook-filter-invalid@example.com", username="cookfilterinvalid")
    token = login_and_get_token(client, identifier="cook-filter-invalid@example.com")

    response = client.get("/recipes?max_cook_time_minutes=0", headers=auth_headers(token))
    assert response.status_code == 422, response.text


def test_owner_can_upload_cover_image(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    register_user(client, email="cover-owner@example.com", username="coverowner")
    token = login_and_get_token(client, identifier="cover-owner@example.com")
    recipe = create_recipe_via_api(client, token, name="Cover Recipe", meal_types=["dinner"])

    response = client.post(
        f"/recipes/{recipe['id']}/cover-image",
        headers=auth_headers(token),
        files={"file": ("cover.png", PNG_BYTES, "image/png")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["image_url"] is not None
    assert payload["image_url"].startswith("/media/recipes/")


def test_non_owner_cannot_upload_cover_image(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    register_user(client, email="cover-owner-2@example.com", username="coverowner2")
    owner_token = login_and_get_token(client, identifier="cover-owner-2@example.com")
    recipe = create_recipe_via_api(client, owner_token, name="Cover Private", meal_types=["dinner"])

    register_user(client, email="cover-foreign@example.com", username="coverforeign")
    foreign_token = login_and_get_token(client, identifier="cover-foreign@example.com")

    response = client.post(
        f"/recipes/{recipe['id']}/cover-image",
        headers=auth_headers(foreign_token),
        files={"file": ("cover.png", PNG_BYTES, "image/png")},
    )
    assert response.status_code == 404, response.text


def test_invalid_cover_content_type_returns_422(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    register_user(client, email="cover-invalid-type@example.com", username="coverinvalidtype")
    token = login_and_get_token(client, identifier="cover-invalid-type@example.com")
    recipe = create_recipe_via_api(client, token, name="Cover Type", meal_types=["dinner"])

    response = client.post(
        f"/recipes/{recipe['id']}/cover-image",
        headers=auth_headers(token),
        files={"file": ("cover.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 422, response.text


def test_too_large_cover_returns_413(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    register_user(client, email="cover-large@example.com", username="coverlarge")
    token = login_and_get_token(client, identifier="cover-large@example.com")
    recipe = create_recipe_via_api(client, token, name="Cover Large", meal_types=["dinner"])

    response = client.post(
        f"/recipes/{recipe['id']}/cover-image",
        headers=auth_headers(token),
        files={"file": ("large.png", b"a" * (5 * 1024 * 1024 + 1), "image/png")},
    )
    assert response.status_code == 413, response.text


def test_owner_can_replace_recipe_steps(client: TestClient) -> None:
    register_user(client, email="steps-owner@example.com", username="stepsowner")
    token = login_and_get_token(client, identifier="steps-owner@example.com")
    recipe = create_recipe_via_api(client, token, name="Steps Recipe", meal_types=["dinner"])

    response = client.put(
        f"/recipes/{recipe['id']}/steps",
        headers=auth_headers(token),
        json={
            "steps": [
                {"text": "Подготовьте ингредиенты", "note": "Нарежьте заранее"},
                {"text": "Готовьте 15 минут"},
            ]
        },
    )
    assert response.status_code == 200, response.text
    steps = response.json()
    assert len(steps) == 2
    assert steps[0]["position"] == 1
    assert steps[1]["position"] == 2


def test_recipe_steps_reorder_is_persisted(client: TestClient) -> None:
    register_user(client, email="steps-reorder@example.com", username="stepsreorder")
    token = login_and_get_token(client, identifier="steps-reorder@example.com")
    recipe = create_recipe_via_api(client, token, name="Steps Reorder", meal_types=["dinner"])

    create_response = client.put(
        f"/recipes/{recipe['id']}/steps",
        headers=auth_headers(token),
        json={
            "steps": [
                {"text": "Шаг 1"},
                {"text": "Шаг 2"},
                {"text": "Шаг 3"},
            ]
        },
    )
    assert create_response.status_code == 200, create_response.text
    created_steps = create_response.json()
    assert [step["text"] for step in created_steps] == ["Шаг 1", "Шаг 2", "Шаг 3"]
    first_id = created_steps[0]["id"]
    second_id = created_steps[1]["id"]
    third_id = created_steps[2]["id"]

    reorder_response = client.put(
        f"/recipes/{recipe['id']}/steps",
        headers=auth_headers(token),
        json={
            "steps": [
                {"id": third_id, "position": 3, "text": "Шаг 3"},
                {"id": first_id, "position": 1, "text": "Шаг 1"},
                {"id": second_id, "position": 2, "text": "Шаг 2"},
            ]
        },
    )
    assert reorder_response.status_code == 200, reorder_response.text
    reordered_steps = reorder_response.json()
    assert [step["id"] for step in reordered_steps] == [third_id, first_id, second_id]
    assert [step["position"] for step in reordered_steps] == [1, 2, 3]

    read_steps_response = client.get(f"/recipes/{recipe['id']}/steps", headers=auth_headers(token))
    assert read_steps_response.status_code == 200, read_steps_response.text
    read_steps = read_steps_response.json()
    assert [step["id"] for step in read_steps] == [third_id, first_id, second_id]
    assert [step["position"] for step in read_steps] == [1, 2, 3]

    recipe_response = client.get(f"/recipes/{recipe['id']}", headers=auth_headers(token))
    assert recipe_response.status_code == 200, recipe_response.text
    recipe_payload = recipe_response.json()
    assert [step["id"] for step in recipe_payload["steps"]] == [third_id, first_id, second_id]
    assert [step["position"] for step in recipe_payload["steps"]] == [1, 2, 3]


def test_replace_recipe_steps_blank_text_returns_422(client: TestClient) -> None:
    register_user(client, email="steps-blank@example.com", username="stepsblank")
    token = login_and_get_token(client, identifier="steps-blank@example.com")
    recipe = create_recipe_via_api(client, token, name="Steps Blank", meal_types=["dinner"])

    response = client.put(
        f"/recipes/{recipe['id']}/steps",
        headers=auth_headers(token),
        json={"steps": [{"text": "   "}]},
    )
    assert response.status_code == 422, response.text


def test_public_reader_can_view_steps_but_cannot_edit(client: TestClient) -> None:
    register_user(client, email="steps-public-owner@example.com", username="stepspublicowner")
    owner_token = login_and_get_token(client, identifier="steps-public-owner@example.com")
    recipe = create_recipe_via_api(client, owner_token, name="Public Steps", meal_types=["dinner"])

    put_owner = client.put(
        f"/recipes/{recipe['id']}/steps",
        headers=auth_headers(owner_token),
        json={"steps": [{"text": "Шаг 1"}]},
    )
    assert put_owner.status_code == 200, put_owner.text
    publish_response = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    register_user(client, email="steps-public-viewer@example.com", username="stepspublicviewer")
    viewer_token = login_and_get_token(client, identifier="steps-public-viewer@example.com")

    get_response = client.get(f"/recipes/{recipe['id']}/steps", headers=auth_headers(viewer_token))
    assert get_response.status_code == 200, get_response.text
    assert len(get_response.json()) == 1

    put_response = client.put(
        f"/recipes/{recipe['id']}/steps",
        headers=auth_headers(viewer_token),
        json={"steps": [{"text": "Чужой шаг"}]},
    )
    assert put_response.status_code == 404, put_response.text


def test_owner_can_upload_step_image_and_public_can_view(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    register_user(client, email="steps-image-owner@example.com", username="stepsimageowner")
    owner_token = login_and_get_token(client, identifier="steps-image-owner@example.com")
    recipe = create_recipe_via_api(client, owner_token, name="Steps Image", meal_types=["dinner"])

    put_steps = client.put(
        f"/recipes/{recipe['id']}/steps",
        headers=auth_headers(owner_token),
        json={"steps": [{"text": "Шаг с фото"}]},
    )
    assert put_steps.status_code == 200, put_steps.text
    step_id = put_steps.json()[0]["id"]

    upload_response = client.post(
        f"/recipes/{recipe['id']}/steps/{step_id}/image",
        headers=auth_headers(owner_token),
        files={"file": ("step.png", PNG_BYTES, "image/png")},
    )
    assert upload_response.status_code == 200, upload_response.text
    assert upload_response.json()["image_url"] is not None

    publish_response = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    register_user(client, email="steps-image-viewer@example.com", username="stepsimageviewer")
    viewer_token = login_and_get_token(client, identifier="steps-image-viewer@example.com")
    get_steps = client.get(f"/recipes/{recipe['id']}/steps", headers=auth_headers(viewer_token))
    assert get_steps.status_code == 200, get_steps.text
    assert get_steps.json()[0]["image_url"] is not None


def test_user_can_add_note_to_own_recipe(client: TestClient) -> None:
    register_user(client, email="note-own@example.com", username="noteown")
    token = login_and_get_token(client, identifier="note-own@example.com")
    recipe = create_recipe_via_api(client, token, name="Свой рецепт")

    put_response = client.put(
        f"/recipes/{recipe['id']}/note",
        headers=auth_headers(token),
        json={"note": "Готовить на медленном огне 10 минут."},
    )
    assert put_response.status_code == 200, put_response.text
    assert put_response.json()["note"] == "Готовить на медленном огне 10 минут."

    get_response = client.get(f"/recipes/{recipe['id']}/note", headers=auth_headers(token))
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["note"] == "Готовить на медленном огне 10 минут."


def test_user_can_add_note_to_public_recipe(client: TestClient) -> None:
    register_user(client, email="note-public-owner@example.com", username="notepublicowner")
    owner_token = login_and_get_token(client, identifier="note-public-owner@example.com")
    recipe = create_recipe_via_api(client, owner_token, name="Публичный рецепт")
    publish_response = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    register_user(client, email="note-public-viewer@example.com", username="notepublicviewer")
    viewer_token = login_and_get_token(client, identifier="note-public-viewer@example.com")

    put_response = client.put(
        f"/recipes/{recipe['id']}/note",
        headers=auth_headers(viewer_token),
        json={"note": "Отлично подходит для ужина."},
    )
    assert put_response.status_code == 200, put_response.text
    assert put_response.json()["note"] == "Отлично подходит для ужина."


def test_user_cannot_add_note_to_inaccessible_private_recipe(client: TestClient) -> None:
    register_user(client, email="note-private-owner@example.com", username="noteprivateowner")
    owner_token = login_and_get_token(client, identifier="note-private-owner@example.com")
    recipe = create_recipe_via_api(client, owner_token, name="Приватный рецепт")

    register_user(client, email="note-private-viewer@example.com", username="noteprivateviewer")
    viewer_token = login_and_get_token(client, identifier="note-private-viewer@example.com")

    response = client.put(
        f"/recipes/{recipe['id']}/note",
        headers=auth_headers(viewer_token),
        json={"note": "Попытка заметки"},
    )
    assert response.status_code == 404, response.text


def test_other_user_does_not_see_my_note(client: TestClient) -> None:
    register_user(client, email="note-owner2@example.com", username="noteowner2")
    owner_token = login_and_get_token(client, identifier="note-owner2@example.com")
    recipe = create_recipe_via_api(client, owner_token, name="Рецепт для заметок")
    publish_response = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    register_user(client, email="note-user-a@example.com", username="noteusera")
    user_a_token = login_and_get_token(client, identifier="note-user-a@example.com")
    register_user(client, email="note-user-b@example.com", username="noteuserb")
    user_b_token = login_and_get_token(client, identifier="note-user-b@example.com")

    put_response = client.put(
        f"/recipes/{recipe['id']}/note",
        headers=auth_headers(user_a_token),
        json={"note": "Моя личная заметка"},
    )
    assert put_response.status_code == 200, put_response.text

    get_response = client.get(f"/recipes/{recipe['id']}/note", headers=auth_headers(user_b_token))
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["note"] is None


def test_update_recipe_note(client: TestClient) -> None:
    register_user(client, email="note-update@example.com", username="noteupdate")
    token = login_and_get_token(client, identifier="note-update@example.com")
    recipe = create_recipe_via_api(client, token, name="Рецепт обновления заметки")

    first_response = client.put(
        f"/recipes/{recipe['id']}/note",
        headers=auth_headers(token),
        json={"note": "Первый вариант"},
    )
    assert first_response.status_code == 200, first_response.text

    second_response = client.put(
        f"/recipes/{recipe['id']}/note",
        headers=auth_headers(token),
        json={"note": "Обновлённый вариант"},
    )
    assert second_response.status_code == 200, second_response.text
    assert second_response.json()["note"] == "Обновлённый вариант"


def test_delete_recipe_note(client: TestClient) -> None:
    register_user(client, email="note-delete@example.com", username="notedelete")
    token = login_and_get_token(client, identifier="note-delete@example.com")
    recipe = create_recipe_via_api(client, token, name="Рецепт удаления заметки")

    put_response = client.put(
        f"/recipes/{recipe['id']}/note",
        headers=auth_headers(token),
        json={"note": "Удаляемая заметка"},
    )
    assert put_response.status_code == 200, put_response.text

    delete_response = client.delete(f"/recipes/{recipe['id']}/note", headers=auth_headers(token))
    assert delete_response.status_code == 204, delete_response.text

    get_response = client.get(f"/recipes/{recipe['id']}/note", headers=auth_headers(token))
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["note"] is None


def test_blank_recipe_note_returns_422(client: TestClient) -> None:
    register_user(client, email="note-blank@example.com", username="noteblank")
    token = login_and_get_token(client, identifier="note-blank@example.com")
    recipe = create_recipe_via_api(client, token, name="Рецепт пустой заметки")

    response = client.put(
        f"/recipes/{recipe['id']}/note",
        headers=auth_headers(token),
        json={"note": "   "},
    )
    assert response.status_code == 422, response.text


def test_copy_public_recipe_creates_own_private_draft(client: TestClient) -> None:
    register_user(client, email="copy-public-owner@example.com", username="copypublicowner")
    owner_token = login_and_get_token(client, identifier="copy-public-owner@example.com")
    food = create_food_via_api(
        client,
        owner_token,
        name="Продукт для копии",
        kcal="100.00",
        protein="10.00",
        fat="5.00",
        carbs="10.00",
    )
    source_recipe = create_recipe_via_api(
        client,
        owner_token,
        name="Публичная копия",
        description="Описание",
        instructions="Шаг 1. Шаг 2.",
        image_url="https://example.com/public-copy.jpg",
        cook_time_minutes=25,
        meal_types=["dinner"],
    )
    add_response = client.post(
        f"/recipes/{source_recipe['id']}/ingredients",
        headers=auth_headers(owner_token),
        json={"food_id": food["id"], "grams": "120"},
    )
    assert add_response.status_code == 201, add_response.text
    steps_response = client.put(
        f"/recipes/{source_recipe['id']}/steps",
        headers=auth_headers(owner_token),
        json={"steps": [{"text": "Подготовьте ингредиенты"}, {"text": "Приготовьте блюдо"}]},
    )
    assert steps_response.status_code == 200, steps_response.text
    publish_response = client.post(f"/recipes/{source_recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    register_user(client, email="copy-public-user@example.com", username="copypublicuser")
    user_token = login_and_get_token(client, identifier="copy-public-user@example.com")

    copy_response = client.post(f"/recipes/{source_recipe['id']}/copy", headers=auth_headers(user_token))
    assert copy_response.status_code == 201, copy_response.text
    copied = copy_response.json()
    assert copied["owner_user_id"] != source_recipe["owner_user_id"]
    assert copied["source"] == "private"
    assert copied["status"] == "draft"
    assert copied["is_listed"] is False
    assert copied["description"] == "Описание"
    assert copied["instructions"] == "Шаг 1. Шаг 2."
    assert copied["image_url"] == "https://example.com/public-copy.jpg"
    assert copied["cook_time_minutes"] == 25
    assert len(copied["ingredients"]) == 1
    assert copied["ingredients"][0]["food_id"] == food["id"]
    assert len(copied.get("steps") or []) == 2


def test_copied_recipe_can_be_edited_by_new_owner(client: TestClient) -> None:
    register_user(client, email="copy-edit-owner@example.com", username="copyeditowner")
    owner_token = login_and_get_token(client, identifier="copy-edit-owner@example.com")
    source_recipe = create_recipe_via_api(client, owner_token, name="Рецепт для копирования")
    publish_response = client.post(f"/recipes/{source_recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    register_user(client, email="copy-edit-user@example.com", username="copyedituser")
    user_token = login_and_get_token(client, identifier="copy-edit-user@example.com")

    copy_response = client.post(f"/recipes/{source_recipe['id']}/copy", headers=auth_headers(user_token))
    assert copy_response.status_code == 201, copy_response.text
    copied_id = copy_response.json()["id"]

    patch_response = client.patch(
        f"/recipes/{copied_id}",
        headers=auth_headers(user_token),
        json={"name": "Моя версия рецепта"},
    )
    assert patch_response.status_code == 200, patch_response.text
    assert patch_response.json()["name"] == "Моя версия рецепта"


def test_copy_inaccessible_private_recipe_returns_404(client: TestClient) -> None:
    register_user(client, email="copy-private-owner@example.com", username="copyprivateowner")
    owner_token = login_and_get_token(client, identifier="copy-private-owner@example.com")
    source_recipe = create_recipe_via_api(client, owner_token, name="Закрытый рецепт")

    register_user(client, email="copy-private-user@example.com", username="copyprivateuser")
    user_token = login_and_get_token(client, identifier="copy-private-user@example.com")

    response = client.post(f"/recipes/{source_recipe['id']}/copy", headers=auth_headers(user_token))
    assert response.status_code == 404, response.text


def test_copy_does_not_modify_original(client: TestClient) -> None:
    register_user(client, email="copy-original-owner@example.com", username="copyoriginalowner")
    owner_token = login_and_get_token(client, identifier="copy-original-owner@example.com")
    source_recipe = create_recipe_via_api(client, owner_token, name="Оригинал рецепта")
    publish_response = client.post(f"/recipes/{source_recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    register_user(client, email="copy-original-user@example.com", username="copyoriginaluser")
    user_token = login_and_get_token(client, identifier="copy-original-user@example.com")

    copy_response = client.post(f"/recipes/{source_recipe['id']}/copy", headers=auth_headers(user_token))
    assert copy_response.status_code == 201, copy_response.text

    original_response = client.get(f"/recipes/{source_recipe['id']}", headers=auth_headers(owner_token))
    assert original_response.status_code == 200, original_response.text
    original = original_response.json()
    assert original["source"] == "community"
    assert original["status"] == "approved"


def test_notes_are_not_copied(client: TestClient) -> None:
    register_user(client, email="copy-note-owner@example.com", username="copynoteowner")
    owner_token = login_and_get_token(client, identifier="copy-note-owner@example.com")
    source_recipe = create_recipe_via_api(client, owner_token, name="Рецепт с заметкой")
    publish_response = client.post(f"/recipes/{source_recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    register_user(client, email="copy-note-user@example.com", username="copynoteuser")
    user_token = login_and_get_token(client, identifier="copy-note-user@example.com")

    note_response = client.put(
        f"/recipes/{source_recipe['id']}/note",
        headers=auth_headers(user_token),
        json={"note": "Личная заметка к оригиналу"},
    )
    assert note_response.status_code == 200, note_response.text

    copy_response = client.post(f"/recipes/{source_recipe['id']}/copy", headers=auth_headers(user_token))
    assert copy_response.status_code == 201, copy_response.text
    copied_id = copy_response.json()["id"]

    copied_note_response = client.get(f"/recipes/{copied_id}/note", headers=auth_headers(user_token))
    assert copied_note_response.status_code == 200, copied_note_response.text
    assert copied_note_response.json()["note"] is None


def test_user_can_favorite_own_recipe(client: TestClient) -> None:
    register_user(client, email="favorite-own@example.com", username="favoriteown")
    token = login_and_get_token(client, identifier="favorite-own@example.com")
    recipe = create_recipe_via_api(client, token, name="Мой избранный рецепт")

    response = client.post(f"/recipes/{recipe['id']}/favorite", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    assert response.json() == {"recipe_id": recipe["id"], "is_favorite": True}

    detail = client.get(f"/recipes/{recipe['id']}", headers=auth_headers(token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["is_favorite"] is True


def test_user_can_favorite_public_recipe(client: TestClient) -> None:
    register_user(client, email="favorite-public-owner@example.com", username="favoritepublicowner")
    owner_token = login_and_get_token(client, identifier="favorite-public-owner@example.com")
    public_recipe = create_recipe_via_api(client, owner_token, name="Публичный рецепт для избранного", meal_types=["dinner"])
    publish_response = client.post(f"/recipes/{public_recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    register_user(client, email="favorite-public-viewer@example.com", username="favoritepublicviewer")
    viewer_token = login_and_get_token(client, identifier="favorite-public-viewer@example.com")

    favorite_response = client.post(f"/recipes/{public_recipe['id']}/favorite", headers=auth_headers(viewer_token))
    assert favorite_response.status_code == 200, favorite_response.text
    assert favorite_response.json()["is_favorite"] is True

    detail = client.get(f"/recipes/{public_recipe['id']}", headers=auth_headers(viewer_token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["is_favorite"] is True


def test_user_cannot_favorite_inaccessible_private_recipe(client: TestClient) -> None:
    register_user(client, email="favorite-private-owner@example.com", username="favoriteprivateowner")
    owner_token = login_and_get_token(client, identifier="favorite-private-owner@example.com")
    private_recipe = create_recipe_via_api(client, owner_token, name="Закрытый рецепт для избранного")

    register_user(client, email="favorite-private-viewer@example.com", username="favoriteprivateviewer")
    viewer_token = login_and_get_token(client, identifier="favorite-private-viewer@example.com")

    response = client.post(f"/recipes/{private_recipe['id']}/favorite", headers=auth_headers(viewer_token))
    assert response.status_code == 404, response.text


def test_duplicate_favorite_and_remove_absent_are_idempotent(client: TestClient) -> None:
    register_user(client, email="favorite-idempotent@example.com", username="favoriteidempotent")
    token = login_and_get_token(client, identifier="favorite-idempotent@example.com")
    recipe = create_recipe_via_api(client, token, name="Идемпотентный рецепт")

    first_add = client.post(f"/recipes/{recipe['id']}/favorite", headers=auth_headers(token))
    assert first_add.status_code == 200, first_add.text
    second_add = client.post(f"/recipes/{recipe['id']}/favorite", headers=auth_headers(token))
    assert second_add.status_code == 200, second_add.text

    first_remove = client.delete(f"/recipes/{recipe['id']}/favorite", headers=auth_headers(token))
    assert first_remove.status_code == 200, first_remove.text
    second_remove = client.delete(f"/recipes/{recipe['id']}/favorite", headers=auth_headers(token))
    assert second_remove.status_code == 200, second_remove.text
    assert second_remove.json()["is_favorite"] is False


def test_list_recipes_includes_is_favorite_and_favorite_only_filter(client: TestClient) -> None:
    register_user(client, email="favorite-list@example.com", username="favoritelist")
    token = login_and_get_token(client, identifier="favorite-list@example.com")
    recipe_a = create_recipe_via_api(client, token, name="Рецепт A")
    recipe_b = create_recipe_via_api(client, token, name="Рецепт B")

    favorite_response = client.post(f"/recipes/{recipe_a['id']}/favorite", headers=auth_headers(token))
    assert favorite_response.status_code == 200, favorite_response.text

    list_response = client.get("/recipes?limit=100", headers=auth_headers(token))
    assert list_response.status_code == 200, list_response.text
    by_id = {item["id"]: item for item in list_response.json()}
    assert by_id[recipe_a["id"]]["is_favorite"] is True
    assert by_id[recipe_b["id"]]["is_favorite"] is False

    favorite_only_response = client.get("/recipes?favorite_only=true&limit=100", headers=auth_headers(token))
    assert favorite_only_response.status_code == 200, favorite_only_response.text
    favorite_only_ids = {item["id"] for item in favorite_only_response.json()}
    assert recipe_a["id"] in favorite_only_ids
    assert recipe_b["id"] not in favorite_only_ids


def test_public_favorite_only_filter_returns_favorited_public_recipes(client: TestClient) -> None:
    register_user(client, email="favorite-public-filter-owner@example.com", username="favoritepublicfilterowner")
    owner_token = login_and_get_token(client, identifier="favorite-public-filter-owner@example.com")
    public_recipe_a = create_recipe_via_api(client, owner_token, name="Публичный избранный A", meal_types=["lunch"])
    public_recipe_b = create_recipe_via_api(client, owner_token, name="Публичный избранный B", meal_types=["lunch"])
    publish_a = client.post(f"/recipes/{public_recipe_a['id']}/publish", headers=auth_headers(owner_token))
    publish_b = client.post(f"/recipes/{public_recipe_b['id']}/publish", headers=auth_headers(owner_token))
    assert publish_a.status_code == 200, publish_a.text
    assert publish_b.status_code == 200, publish_b.text

    register_user(client, email="favorite-public-filter-viewer@example.com", username="favoritepublicfilterviewer")
    viewer_token = login_and_get_token(client, identifier="favorite-public-filter-viewer@example.com")

    favorite_response = client.post(f"/recipes/{public_recipe_a['id']}/favorite", headers=auth_headers(viewer_token))
    assert favorite_response.status_code == 200, favorite_response.text

    list_response = client.get(
        "/recipes?include_public=true&favorite_only=true&limit=200",
        headers=auth_headers(viewer_token),
    )
    assert list_response.status_code == 200, list_response.text
    ids = {item["id"] for item in list_response.json()}
    assert public_recipe_a["id"] in ids
    assert public_recipe_b["id"] not in ids
