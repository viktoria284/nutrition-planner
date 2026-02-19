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
