from sqlalchemy.orm import Session, sessionmaker

from fastapi.testclient import TestClient

from app.services.recipes import seed_demo_public_recipes
from tests.test_recipes import auth_headers, login_and_get_token, register_user


def test_public_seed_without_meal_filter_returns_all_meal_types(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
    finally:
        db.close()

    register_user(client, email="seed-viewer@example.com", username="seedviewer")
    token = login_and_get_token(client, identifier="seed-viewer@example.com")

    response = client.get("/recipes?include_public=true&limit=1000", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    data = response.json()
    meal_types: set[str] = set()
    for item in data:
        for meal_type in item.get("meal_types") or []:
            meal_types.add(meal_type)
    assert {"breakfast", "lunch", "dinner", "snack"}.issubset(meal_types)


def test_public_seed_meal_type_breakfast_filter(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
    finally:
        db.close()

    register_user(client, email="seed-breakfast-viewer@example.com", username="seedbreakfastviewer")
    token = login_and_get_token(client, identifier="seed-breakfast-viewer@example.com")

    response = client.get(
        "/recipes?include_public=true&meal_type=breakfast&limit=1000",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) > 0
    assert all("breakfast" in item.get("meal_types", []) for item in data)


def test_public_seed_meal_type_lunch_filter(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
    finally:
        db.close()

    register_user(client, email="seed-lunch-viewer@example.com", username="seedlunchviewer")
    token = login_and_get_token(client, identifier="seed-lunch-viewer@example.com")

    response = client.get(
        "/recipes?include_public=true&meal_type=lunch&limit=1000",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) > 0
    assert all("lunch" in item.get("meal_types", []) for item in data)
