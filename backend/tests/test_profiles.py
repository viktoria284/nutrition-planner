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


def create_food(
    client: TestClient,
    token: str,
    *,
    name: str,
) -> dict:
    response = client.post(
        "/foods",
        headers=auth_headers(token),
        json={
            "name": name,
            "kcal": "100.00",
            "protein": "10.00",
            "fat": "5.00",
            "carbs": "12.00",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_register_creates_default_profile(client: TestClient) -> None:
    user = register_user(
        client,
        email="user1@example.com",
        username="userone",
    )
    token = login_and_get_token(client, identifier="user1@example.com")

    response = client.get("/profiles", headers=auth_headers(token))
    assert response.status_code == 200, response.text

    profiles = response.json()
    assert len(profiles) == 1
    assert profiles[0]["name"] == "Мой профиль"
    assert profiles[0]["user_id"] == user["id"]


def test_user_sees_only_own_profiles(client: TestClient) -> None:
    register_user(
        client,
        email="user1@example.com",
        username="userone",
    )
    token_user1 = login_and_get_token(client, identifier="user1@example.com")
    create_extra = client.post(
        "/profiles",
        headers=auth_headers(token_user1),
        json={"name": "User 1 extra profile", "target_kcal": 1800},
    )
    assert create_extra.status_code == 201, create_extra.text

    user2 = register_user(
        client,
        email="user2@example.com",
        username="usertwo",
    )
    token_user2 = login_and_get_token(client, identifier="user2@example.com")

    response = client.get("/profiles", headers=auth_headers(token_user2))
    assert response.status_code == 200, response.text

    profiles = response.json()
    assert len(profiles) == 1
    assert profiles[0]["name"] == "Мой профиль"
    assert profiles[0]["user_id"] == user2["id"]
    assert all(profile["name"] != "User 1 extra profile" for profile in profiles)


def test_cannot_patch_foreign_profile_returns_404(client: TestClient) -> None:
    register_user(
        client,
        email="user1@example.com",
        username="userone",
    )
    token_user1 = login_and_get_token(client, identifier="user1@example.com")
    user1_profiles = client.get("/profiles", headers=auth_headers(token_user1))
    assert user1_profiles.status_code == 200, user1_profiles.text
    foreign_profile_id = user1_profiles.json()[0]["id"]

    register_user(
        client,
        email="user2@example.com",
        username="usertwo",
    )
    token_user2 = login_and_get_token(client, identifier="user2@example.com")

    response = client.patch(
        f"/profiles/{foreign_profile_id}",
        headers=auth_headers(token_user2),
        json={"name": "Hacked"},
    )
    assert response.status_code == 404, response.text


def test_profile_targets_validation(client: TestClient) -> None:
    register_user(
        client,
        email="user1@example.com",
        username="userone",
    )
    token = login_and_get_token(client, identifier="user1@example.com")
    profile_response = client.get("/profiles", headers=auth_headers(token))
    assert profile_response.status_code == 200, profile_response.text
    profile_id = profile_response.json()[0]["id"]

    response = client.patch(
        f"/profiles/{profile_id}",
        headers=auth_headers(token),
        json={"target_kcal": -1},
    )
    assert response.status_code == 422, response.text


def test_profile_target_fiber_create_patch_and_read(client: TestClient) -> None:
    register_user(client, email="profile-fiber@example.com", username="profilefiber")
    token = login_and_get_token(client, identifier="profile-fiber@example.com")

    create_response = client.post(
        "/profiles",
        headers=auth_headers(token),
        json={"name": "С клетчаткой", "target_fiber": 25},
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["target_fiber"] == 25

    patch_response = client.patch(
        f"/profiles/{created['id']}",
        headers=auth_headers(token),
        json={"target_fiber": 30},
    )
    assert patch_response.status_code == 200, patch_response.text
    assert patch_response.json()["target_fiber"] == 30

    profiles_response = client.get("/profiles", headers=auth_headers(token))
    assert profiles_response.status_code == 200, profiles_response.text
    reloaded = next(item for item in profiles_response.json() if item["id"] == created["id"])
    assert reloaded["target_fiber"] == 30


def test_profile_target_fiber_validation(client: TestClient) -> None:
    register_user(client, email="profile-fiber-invalid@example.com", username="profilefiberinvalid")
    token = login_and_get_token(client, identifier="profile-fiber-invalid@example.com")

    create_negative = client.post(
        "/profiles",
        headers=auth_headers(token),
        json={"name": "Invalid fiber", "target_fiber": -1},
    )
    assert create_negative.status_code == 422, create_negative.text

    create_high = client.post(
        "/profiles",
        headers=auth_headers(token),
        json={"name": "Invalid fiber high", "target_fiber": 101},
    )
    assert create_high.status_code == 422, create_high.text


def test_profile_can_save_excluded_food(client: TestClient) -> None:
    register_user(client, email="profile-excluded@example.com", username="profileexcluded")
    token = login_and_get_token(client, identifier="profile-excluded@example.com")
    food = create_food(client, token, name="Исключаемый продукт")

    profiles = client.get("/profiles", headers=auth_headers(token))
    assert profiles.status_code == 200, profiles.text
    profile_id = profiles.json()[0]["id"]

    response = client.patch(
        f"/profiles/{profile_id}",
        headers=auth_headers(token),
        json={"excluded_food_ids": [food["id"]]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["excluded_food_ids"] == [food["id"]]


def test_profile_can_save_preferred_food(client: TestClient) -> None:
    register_user(client, email="profile-preferred@example.com", username="profilepreferred")
    token = login_and_get_token(client, identifier="profile-preferred@example.com")
    food = create_food(client, token, name="Предпочитаемый продукт")

    profiles = client.get("/profiles", headers=auth_headers(token))
    assert profiles.status_code == 200, profiles.text
    profile_id = profiles.json()[0]["id"]

    response = client.patch(
        f"/profiles/{profile_id}",
        headers=auth_headers(token),
        json={"preferred_food_ids": [food["id"]]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["preferred_food_ids"] == [food["id"]]


def test_profile_can_save_preferred_categories(client: TestClient) -> None:
    register_user(client, email="profile-categories@example.com", username="profilecategories")
    token = login_and_get_token(client, identifier="profile-categories@example.com")
    profiles = client.get("/profiles", headers=auth_headers(token))
    assert profiles.status_code == 200, profiles.text
    profile_id = profiles.json()[0]["id"]

    response = client.patch(
        f"/profiles/{profile_id}",
        headers=auth_headers(token),
        json={"preferred_categories": ["meat_fish", "vegetables"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["preferred_categories"] == ["meat_fish", "vegetables"]


def test_profile_can_save_excluded_categories(client: TestClient) -> None:
    register_user(client, email="profile-excluded-categories@example.com", username="profileexcludedcategories")
    token = login_and_get_token(client, identifier="profile-excluded-categories@example.com")
    profiles = client.get("/profiles", headers=auth_headers(token))
    assert profiles.status_code == 200, profiles.text
    profile_id = profiles.json()[0]["id"]

    response = client.patch(
        f"/profiles/{profile_id}",
        headers=auth_headers(token),
        json={"excluded_categories": ["dairy", "meat_fish"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["excluded_categories"] == ["dairy", "meat_fish"]


def test_profile_can_save_excluded_terms_and_normalizes_duplicates(client: TestClient) -> None:
    register_user(client, email="profile-excluded-terms@example.com", username="profileexcludedterms")
    token = login_and_get_token(client, identifier="profile-excluded-terms@example.com")
    profiles = client.get("/profiles", headers=auth_headers(token))
    assert profiles.status_code == 200, profiles.text
    profile_id = profiles.json()[0]["id"]

    response = client.patch(
        f"/profiles/{profile_id}",
        headers=auth_headers(token),
        json={"excluded_terms": ["  Молоко  ", "молоко", " АРАХИС ", " "]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["excluded_terms"] == ["молоко", "арахис"]


def test_profile_rejects_invalid_excluded_category(client: TestClient) -> None:
    register_user(client, email="profile-invalid-excluded-category@example.com", username="profileinvalidexcludedcategory")
    token = login_and_get_token(client, identifier="profile-invalid-excluded-category@example.com")
    profiles = client.get("/profiles", headers=auth_headers(token))
    assert profiles.status_code == 200, profiles.text
    profile_id = profiles.json()[0]["id"]

    response = client.patch(
        f"/profiles/{profile_id}",
        headers=auth_headers(token),
        json={"excluded_categories": ["unknown_category"]},
    )
    assert response.status_code == 422, response.text


def test_profile_rejects_too_short_excluded_term(client: TestClient) -> None:
    register_user(client, email="profile-invalid-excluded-term@example.com", username="profileinvalidexcludedterm")
    token = login_and_get_token(client, identifier="profile-invalid-excluded-term@example.com")
    profiles = client.get("/profiles", headers=auth_headers(token))
    assert profiles.status_code == 200, profiles.text
    profile_id = profiles.json()[0]["id"]

    response = client.patch(
        f"/profiles/{profile_id}",
        headers=auth_headers(token),
        json={"excluded_terms": ["а"]},
    )
    assert response.status_code == 422, response.text


def test_profile_rejects_same_food_in_excluded_and_preferred(client: TestClient) -> None:
    register_user(client, email="profile-conflict-food@example.com", username="profileconflictfood")
    token = login_and_get_token(client, identifier="profile-conflict-food@example.com")
    food = create_food(client, token, name="Конфликтный продукт")

    profiles = client.get("/profiles", headers=auth_headers(token))
    assert profiles.status_code == 200, profiles.text
    profile_id = profiles.json()[0]["id"]

    response = client.patch(
        f"/profiles/{profile_id}",
        headers=auth_headers(token),
        json={
            "excluded_food_ids": [food["id"]],
            "preferred_food_ids": [food["id"]],
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "Продукт не может одновременно быть в исключениях и предпочтениях."


def test_profile_rejects_same_category_in_excluded_and_preferred(client: TestClient) -> None:
    register_user(client, email="profile-conflict-category@example.com", username="profileconflictcategory")
    token = login_and_get_token(client, identifier="profile-conflict-category@example.com")

    profiles = client.get("/profiles", headers=auth_headers(token))
    assert profiles.status_code == 200, profiles.text
    profile_id = profiles.json()[0]["id"]

    response = client.patch(
        f"/profiles/{profile_id}",
        headers=auth_headers(token),
        json={
            "excluded_categories": ["dairy"],
            "preferred_categories": ["dairy"],
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "Категория не может одновременно быть исключённой и предпочитаемой."


def test_profile_rejects_preferred_food_inside_excluded_category(client: TestClient) -> None:
    register_user(client, email="profile-conflict-food-category@example.com", username="profileconflictfoodcategory")
    token = login_and_get_token(client, identifier="profile-conflict-food-category@example.com")
    food_response = client.post(
        "/foods",
        headers=auth_headers(token),
        json={
            "name": "Молоко пастеризованное",
            "category": "dairy",
            "kcal": "52.00",
            "protein": "2.80",
            "fat": "2.50",
            "carbs": "4.70",
        },
    )
    assert food_response.status_code == 201, food_response.text
    dairy_food = food_response.json()

    profiles = client.get("/profiles", headers=auth_headers(token))
    assert profiles.status_code == 200, profiles.text
    profile_id = profiles.json()[0]["id"]

    response = client.patch(
        f"/profiles/{profile_id}",
        headers=auth_headers(token),
        json={
            "excluded_categories": ["dairy"],
            "preferred_food_ids": [dairy_food["id"]],
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "Предпочитаемый продукт относится к исключённой категории."


def test_profile_max_cook_time_validation(client: TestClient) -> None:
    register_user(client, email="profile-max-cook@example.com", username="profilemaxcook")
    token = login_and_get_token(client, identifier="profile-max-cook@example.com")
    profiles = client.get("/profiles", headers=auth_headers(token))
    assert profiles.status_code == 200, profiles.text
    profile_id = profiles.json()[0]["id"]

    response = client.patch(
        f"/profiles/{profile_id}",
        headers=auth_headers(token),
        json={"max_cook_time_minutes": 0},
    )
    assert response.status_code == 422, response.text


def test_profile_cannot_add_foreign_private_food_to_preferences(client: TestClient) -> None:
    register_user(client, email="profile-owner@example.com", username="profileowner")
    owner_token = login_and_get_token(client, identifier="profile-owner@example.com")
    foreign_food = create_food(client, owner_token, name="Чужой продукт")

    register_user(client, email="profile-other@example.com", username="profileother")
    other_token = login_and_get_token(client, identifier="profile-other@example.com")
    other_profiles = client.get("/profiles", headers=auth_headers(other_token))
    assert other_profiles.status_code == 200, other_profiles.text
    other_profile_id = other_profiles.json()[0]["id"]

    response = client.patch(
        f"/profiles/{other_profile_id}",
        headers=auth_headers(other_token),
        json={"preferred_food_ids": [foreign_food["id"]]},
    )
    assert response.status_code == 404, response.text


def test_read_profile_returns_restrictions_and_preferences(client: TestClient) -> None:
    register_user(client, email="profile-read-extra@example.com", username="profilereadextra")
    token = login_and_get_token(client, identifier="profile-read-extra@example.com")
    excluded = create_food(client, token, name="Исключаемый")
    preferred = create_food(client, token, name="Предпочитаемый")

    profiles = client.get("/profiles", headers=auth_headers(token))
    assert profiles.status_code == 200, profiles.text
    profile_id = profiles.json()[0]["id"]

    patch_response = client.patch(
        f"/profiles/{profile_id}",
        headers=auth_headers(token),
        json={
            "excluded_food_ids": [excluded["id"]],
            "excluded_categories": ["dairy"],
            "excluded_terms": ["молоко"],
            "preferred_food_ids": [preferred["id"]],
            "preferred_categories": ["fruits"],
            "max_cook_time_minutes": 45,
        },
    )
    assert patch_response.status_code == 200, patch_response.text

    get_response = client.get("/profiles", headers=auth_headers(token))
    assert get_response.status_code == 200, get_response.text
    profile = next(item for item in get_response.json() if item["id"] == profile_id)
    assert profile["excluded_food_ids"] == [excluded["id"]]
    assert profile["excluded_categories"] == ["dairy"]
    assert profile["excluded_terms"] == ["молоко"]
    assert profile["preferred_food_ids"] == [preferred["id"]]
    assert profile["preferred_categories"] == ["fruits"]
    assert profile["max_cook_time_minutes"] == 45
