from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.profile_target_calculation import ProfileTargetCalculation

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


def default_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "sex": "female",
        "age": 25,
        "height_cm": 165,
        "weight_kg": 60,
        "activity_level": "moderate",
        "goal": "maintain",
        "formula": "mifflin_st_jeor",
        "macro_preset": "balanced",
        "special_condition": "none",
        "lactation_period": None,
    }
    payload.update(overrides)
    return payload


def calculate(client: TestClient, token: str, payload: dict[str, object]) -> dict:
    response = client.post(
        "/profile-target-calculations/calculate",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


def get_default_profile_id(client: TestClient, token: str) -> int:
    response = client.get("/profiles", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()[0]["id"]


def test_calculate_mifflin_st_jeor_female_default_case(client: TestClient) -> None:
    register_user(client, email="calc-mifflin-female-default@example.com", username="calcmifflinfemaledefault")
    token = login_and_get_token(client, identifier="calc-mifflin-female-default@example.com")

    result = calculate(client, token, default_payload())

    assert result["bmr"] == 1345
    assert result["tdee"] == 2085
    assert result["target_kcal"] == 2085


def test_formula_default_is_mifflin_st_jeor_when_omitted(client: TestClient) -> None:
    register_user(client, email="calc-default-formula@example.com", username="calcdefaultformula")
    token = login_and_get_token(client, identifier="calc-default-formula@example.com")

    payload = default_payload()
    payload.pop("formula")
    result = calculate(client, token, payload)

    assert result["formula"] == "mifflin_st_jeor"


def test_calculate_who_fao_unu_for_adults(client: TestClient) -> None:
    register_user(client, email="calc-who-adult@example.com", username="calcwhoadult")
    token = login_and_get_token(client, identifier="calc-who-adult@example.com")

    payload = default_payload(formula="who_fao_unu", sex="male", age=61, weight_kg=72)
    result = calculate(client, token, payload)

    assert result["bmr"] == 1459
    assert result["tdee"] == 2261
    assert result["target_kcal"] == 2261


def test_target_fiber_default_is_25(client: TestClient) -> None:
    register_user(client, email="calc-fiber-default@example.com", username="calcfiberdefault")
    token = login_and_get_token(client, identifier="calc-fiber-default@example.com")

    result = calculate(client, token, default_payload())

    assert result["target_fiber"] == 25.0


def test_breastfeeding_first_6_months_adds_330_kcal(client: TestClient) -> None:
    register_user(client, email="calc-bf-6m@example.com", username="calcbf6m")
    token = login_and_get_token(client, identifier="calc-bf-6m@example.com")

    baseline = calculate(client, token, default_payload(special_condition="none"))
    breastfeeding = calculate(
        client,
        token,
        default_payload(special_condition="breastfeeding", lactation_period="first_6_months"),
    )

    assert breastfeeding["target_kcal"] - baseline["target_kcal"] == 330


def test_breastfeeding_after_6_months_adds_400_kcal(client: TestClient) -> None:
    register_user(client, email="calc-bf-after6@example.com", username="calcbfafter6")
    token = login_and_get_token(client, identifier="calc-bf-after6@example.com")

    baseline = calculate(client, token, default_payload(special_condition="none"))
    breastfeeding = calculate(
        client,
        token,
        default_payload(special_condition="breastfeeding", lactation_period="after_6_months"),
    )

    assert breastfeeding["target_kcal"] - baseline["target_kcal"] == 400


def test_breastfeeding_macros_recalculated_from_final_target_kcal(client: TestClient) -> None:
    register_user(client, email="calc-bf-macros@example.com", username="calcbfmacros")
    token = login_and_get_token(client, identifier="calc-bf-macros@example.com")

    result = calculate(
        client,
        token,
        default_payload(
            special_condition="breastfeeding",
            lactation_period="first_6_months",
            macro_preset="higher_protein",
        ),
    )

    expected_protein = round((result["target_kcal"] * 0.25 / 4), 1)
    expected_fat = round((result["target_kcal"] * 0.30 / 9), 1)
    expected_carbs = round((result["target_kcal"] * 0.45 / 4), 1)

    assert result["target_protein"] == expected_protein
    assert result["target_fat"] == expected_fat
    assert result["target_carbs"] == expected_carbs


def test_pregnant_does_not_add_kcal_and_returns_warning(client: TestClient) -> None:
    register_user(client, email="calc-pregnant@example.com", username="calcpregnant")
    token = login_and_get_token(client, identifier="calc-pregnant@example.com")

    baseline = calculate(client, token, default_payload(special_condition="none"))
    pregnant = calculate(client, token, default_payload(special_condition="pregnant"))

    assert pregnant["target_kcal"] == baseline["target_kcal"]
    assert pregnant["warning_message"] is not None
    assert "Во время беременности" in pregnant["warning_message"]


def test_medical_special_diet_does_not_change_kcal_and_returns_warning(client: TestClient) -> None:
    register_user(client, email="calc-medical-special-diet@example.com", username="calcmedicalspecialdiet")
    token = login_and_get_token(client, identifier="calc-medical-special-diet@example.com")

    baseline = calculate(client, token, default_payload(special_condition="none"))
    medical = calculate(client, token, default_payload(special_condition="medical_special_diet"))

    assert medical["target_kcal"] == baseline["target_kcal"]
    assert medical["warning_message"] is not None
    assert "лечебного питания" in medical["warning_message"]


def test_get_latest_without_calculation_returns_404(client: TestClient) -> None:
    register_user(client, email="calc-latest-none@example.com", username="calclatestnone")
    token = login_and_get_token(client, identifier="calc-latest-none@example.com")

    response = client.get("/profile-target-calculations/latest", headers=auth_headers(token))

    assert response.status_code == 404


def test_post_calculate_creates_or_updates_single_latest_record(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    register_user(client, email="calc-upsert@example.com", username="calcupsert")
    token = login_and_get_token(client, identifier="calc-upsert@example.com")

    first = calculate(client, token, default_payload(goal="maintain"))
    second = calculate(client, token, default_payload(goal="lose"))

    assert first["id"] == second["id"]

    with db_session_factory() as db:
        count = db.execute(select(func.count(ProfileTargetCalculation.id))).scalar_one()
        assert count == 1


def test_apply_latest_calculation_updates_existing_profile(client: TestClient) -> None:
    register_user(client, email="calc-apply@example.com", username="calcapply")
    token = login_and_get_token(client, identifier="calc-apply@example.com")

    latest = calculate(client, token, default_payload(macro_preset="higher_protein"))
    profile_id = get_default_profile_id(client, token)

    response = client.post(
        f"/profiles/{profile_id}/apply-latest-calculation",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text

    updated_profile = response.json()
    assert updated_profile["target_kcal"] == latest["target_kcal"]
    assert updated_profile["target_protein"] == round(latest["target_protein"])
    assert updated_profile["target_fat"] == round(latest["target_fat"])
    assert updated_profile["target_carbs"] == round(latest["target_carbs"])
    assert updated_profile["target_fiber"] == round(latest["target_fiber"])


def test_cannot_apply_latest_calculation_to_foreign_profile(client: TestClient) -> None:
    register_user(client, email="calc-owner@example.com", username="calcowner")
    owner_token = login_and_get_token(client, identifier="calc-owner@example.com")
    calculate(client, owner_token, default_payload())
    owner_profile_id = get_default_profile_id(client, owner_token)

    register_user(client, email="calc-guest@example.com", username="calcguest")
    guest_token = login_and_get_token(client, identifier="calc-guest@example.com")

    response = client.post(
        f"/profiles/{owner_profile_id}/apply-latest-calculation",
        headers=auth_headers(guest_token),
    )
    assert response.status_code == 404, response.text


def test_invalid_age_height_weight_rejected(client: TestClient) -> None:
    register_user(client, email="calc-invalid@example.com", username="calcinvalid")
    token = login_and_get_token(client, identifier="calc-invalid@example.com")

    invalid_payloads = [
        default_payload(age=17),
        default_payload(height_cm=99),
        default_payload(weight_kg=29),
    ]

    for payload in invalid_payloads:
        response = client.post(
            "/profile-target-calculations/calculate",
            headers=auth_headers(token),
            json=payload,
        )
        assert response.status_code == 422, response.text
