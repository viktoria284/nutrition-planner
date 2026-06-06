from fastapi.testclient import TestClient

TEST_PASSWORD = "Password_123!"


def register_user(client: TestClient, *, email: str, username: str, password: str = TEST_PASSWORD) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "username": username,
            "password": password,
            "display_name": None,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def login_and_get_token(client: TestClient, *, identifier: str, password: str = TEST_PASSWORD) -> str:
    response = client.post(
        "/auth/login",
        data={"username": identifier, "password": password, "grant_type": "password"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_user_can_update_username(client: TestClient) -> None:
    register_user(client, email="update-name@example.com", username="updatename")
    token = login_and_get_token(client, identifier="update-name@example.com")

    response = client.patch("/auth/me", json={"username": "updated_name"}, headers=auth_headers(token))

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["username"] == "updated_name"


def test_update_username_conflict_returns_409(client: TestClient) -> None:
    register_user(client, email="user-a@example.com", username="usera")
    register_user(client, email="user-b@example.com", username="userb")
    token = login_and_get_token(client, identifier="user-a@example.com")

    response = client.patch("/auth/me", json={"username": "userb"}, headers=auth_headers(token))

    assert response.status_code == 409, response.text


def test_user_cannot_update_email(client: TestClient) -> None:
    register_user(client, email="old-email@example.com", username="emailupdate")
    token = login_and_get_token(client, identifier="old-email@example.com")

    response = client.patch("/auth/me", json={"email": "new-email@example.com"}, headers=auth_headers(token))

    assert response.status_code == 422, response.text

    old_login_response = client.post(
        "/auth/login",
        data={"username": "old-email@example.com", "password": TEST_PASSWORD, "grant_type": "password"},
    )
    assert old_login_response.status_code == 200, old_login_response.text

    new_login_response = client.post(
        "/auth/login",
        data={"username": "new-email@example.com", "password": TEST_PASSWORD, "grant_type": "password"},
    )
    assert new_login_response.status_code == 401, new_login_response.text


def test_update_email_payload_is_rejected_before_conflict_check(client: TestClient) -> None:
    register_user(client, email="mail-a@example.com", username="maila")
    register_user(client, email="mail-b@example.com", username="mailb")
    token = login_and_get_token(client, identifier="mail-a@example.com")

    response = client.patch("/auth/me", json={"email": "mail-b@example.com"}, headers=auth_headers(token))

    assert response.status_code == 422, response.text


def test_update_invalid_email_returns_422(client: TestClient) -> None:
    register_user(client, email="invalid-email-user@example.com", username="invalidmail")
    token = login_and_get_token(client, identifier="invalid-email-user@example.com")

    response = client.patch("/auth/me", json={"email": "invalid-email"}, headers=auth_headers(token))

    assert response.status_code == 422, response.text


def test_update_me_requires_auth(client: TestClient) -> None:
    response = client.patch("/auth/me", json={"username": "anonymous"})
    assert response.status_code == 401, response.text


def test_user_can_change_password_and_login_with_new_password(client: TestClient) -> None:
    register_user(client, email="change-pass@example.com", username="changepass")
    token = login_and_get_token(client, identifier="change-pass@example.com")

    response = client.patch(
        "/auth/me/password",
        json={"current_password": TEST_PASSWORD, "new_password": "NewPassword_123!"},
        headers=auth_headers(token),
    )
    assert response.status_code == 204, response.text

    old_login = client.post(
        "/auth/login",
        data={"username": "change-pass@example.com", "password": TEST_PASSWORD, "grant_type": "password"},
    )
    assert old_login.status_code == 401, old_login.text

    new_login = client.post(
        "/auth/login",
        data={"username": "change-pass@example.com", "password": "NewPassword_123!", "grant_type": "password"},
    )
    assert new_login.status_code == 200, new_login.text


def test_change_password_wrong_current_returns_400(client: TestClient) -> None:
    register_user(client, email="wrong-current@example.com", username="wrongcurrent")
    token = login_and_get_token(client, identifier="wrong-current@example.com")

    response = client.patch(
        "/auth/me/password",
        json={"current_password": "WrongPassword_123!", "new_password": "NewPassword_123!"},
        headers=auth_headers(token),
    )
    assert response.status_code == 400, response.text


def test_change_password_requires_auth(client: TestClient) -> None:
    response = client.patch(
        "/auth/me/password",
        json={"current_password": TEST_PASSWORD, "new_password": "NewPassword_123!"},
    )
    assert response.status_code == 401, response.text
