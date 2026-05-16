from fastapi.testclient import TestClient

from tests.test_recipes import auth_headers, create_recipe_via_api, login_and_get_token, register_user


def test_user_can_favorite_author_with_public_recipes(client: TestClient) -> None:
    owner = register_user(client, email="fav-author-owner@example.com", username="favauthorowner")
    owner_token = login_and_get_token(client, identifier="fav-author-owner@example.com")
    viewer_token = login_and_get_token(
        client,
        identifier=register_user(client, email="fav-author-viewer@example.com", username="favauthorviewer")["email"],
    )

    recipe = create_recipe_via_api(client, owner_token, name="Public by author", meal_types=["dinner"])
    publish_response = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    favorite_response = client.post(
        f"/users/{owner['id']}/favorite-author",
        headers=auth_headers(viewer_token),
    )
    assert favorite_response.status_code == 200, favorite_response.text
    payload = favorite_response.json()
    assert payload["author_id"] == owner["id"]
    assert payload["is_favorite"] is True

    list_response = client.get("/users/favorite-authors", headers=auth_headers(viewer_token))
    assert list_response.status_code == 200, list_response.text
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["id"] == owner["id"]
    assert items[0]["username"] == "favauthorowner"
    assert items[0]["public_recipes_count"] >= 1


def test_user_cannot_favorite_self(client: TestClient) -> None:
    user = register_user(client, email="fav-author-self@example.com", username="favauthorself")
    token = login_and_get_token(client, identifier="fav-author-self@example.com")

    response = client.post(f"/users/{user['id']}/favorite-author", headers=auth_headers(token))
    assert response.status_code == 422, response.text


def test_duplicate_favorite_author_is_idempotent(client: TestClient) -> None:
    owner = register_user(client, email="fav-author-dup-owner@example.com", username="favauthordupowner")
    owner_token = login_and_get_token(client, identifier="fav-author-dup-owner@example.com")
    viewer_token = login_and_get_token(
        client,
        identifier=register_user(client, email="fav-author-dup-viewer@example.com", username="favauthordupviewer")["email"],
    )

    recipe = create_recipe_via_api(client, owner_token, name="Dup author public", meal_types=["breakfast"])
    publish_response = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    first = client.post(f"/users/{owner['id']}/favorite-author", headers=auth_headers(viewer_token))
    second = client.post(f"/users/{owner['id']}/favorite-author", headers=auth_headers(viewer_token))
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    items = client.get("/users/favorite-authors", headers=auth_headers(viewer_token)).json()
    assert len(items) == 1


def test_remove_favorite_author_works(client: TestClient) -> None:
    owner = register_user(client, email="fav-author-rem-owner@example.com", username="favauthorremowner")
    owner_token = login_and_get_token(client, identifier="fav-author-rem-owner@example.com")
    viewer_token = login_and_get_token(
        client,
        identifier=register_user(client, email="fav-author-rem-viewer@example.com", username="favauthorremviewer")["email"],
    )

    recipe = create_recipe_via_api(client, owner_token, name="Remove author public", meal_types=["lunch"])
    publish_response = client.post(f"/recipes/{recipe['id']}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    add_response = client.post(f"/users/{owner['id']}/favorite-author", headers=auth_headers(viewer_token))
    assert add_response.status_code == 200, add_response.text

    remove_response = client.delete(f"/users/{owner['id']}/favorite-author", headers=auth_headers(viewer_token))
    assert remove_response.status_code == 200, remove_response.text
    assert remove_response.json()["is_favorite"] is False

    list_response = client.get("/users/favorite-authors", headers=auth_headers(viewer_token))
    assert list_response.status_code == 200, list_response.text
    assert list_response.json() == []


def test_cannot_favorite_author_without_public_recipes(client: TestClient) -> None:
    owner = register_user(client, email="fav-author-private-owner@example.com", username="favauthorprivateowner")
    viewer_token = login_and_get_token(
        client,
        identifier=register_user(client, email="fav-author-private-viewer@example.com", username="favauthorprivateviewer")["email"],
    )

    response = client.post(f"/users/{owner['id']}/favorite-author", headers=auth_headers(viewer_token))
    assert response.status_code == 422, response.text


def test_public_recipes_can_filter_by_favorite_authors(client: TestClient) -> None:
    author_a = register_user(client, email="fav-filter-a@example.com", username="favfiltera")
    token_a = login_and_get_token(client, identifier="fav-filter-a@example.com")
    author_b = register_user(client, email="fav-filter-b@example.com", username="favfilterb")
    token_b = login_and_get_token(client, identifier="fav-filter-b@example.com")

    viewer = register_user(client, email="fav-filter-viewer@example.com", username="favfilterviewer")
    viewer_token = login_and_get_token(client, identifier="fav-filter-viewer@example.com")

    public_a = create_recipe_via_api(client, token_a, name="Fav A Public", meal_types=["dinner"])
    private_a = create_recipe_via_api(client, token_a, name="Fav A Private", meal_types=["dinner"])
    public_b = create_recipe_via_api(client, token_b, name="Fav B Public", meal_types=["dinner"])

    assert client.post(f"/recipes/{public_a['id']}/publish", headers=auth_headers(token_a)).status_code == 200
    assert client.post(f"/recipes/{public_b['id']}/publish", headers=auth_headers(token_b)).status_code == 200

    favorite_response = client.post(
        f"/users/{author_a['id']}/favorite-author",
        headers=auth_headers(viewer_token),
    )
    assert favorite_response.status_code == 200, favorite_response.text

    response = client.get(
        "/recipes?include_public=true&favorite_authors_only=true&limit=100",
        headers=auth_headers(viewer_token),
    )
    assert response.status_code == 200, response.text
    items = response.json()

    ids = {item["id"] for item in items}
    assert public_a["id"] in ids
    assert public_b["id"] not in ids
    assert private_a["id"] not in ids
    assert all(item["author_id"] == author_a["id"] for item in items)
