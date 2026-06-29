from fastapi.testclient import TestClient

from tests.test_auth_users import login, register_user


def vehicle_payload(
    *,
    plate: str = "abc-1d23",
    chassis: str = "9BWZZZ377VT004251",
    renavam: str = "12345678901",
) -> dict[str, object]:
    return {
        "plate": plate,
        "brand": "Volkswagen",
        "model": "Golf",
        "model_year": 2020,
        "color": "Prata",
        "vehicle_type": "car",
        "chassis": chassis,
        "renavam": renavam,
        "fuel_type": "flex",
        "engine": "1.4 TSI",
        "transmission": "automatic",
    }


def auth_headers(client: TestClient) -> dict[str, str]:
    register_user(client)
    token = login(client)
    return {"Authorization": f"Bearer {token}"}


def test_create_vehicle_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/v1/vehicles", json=vehicle_payload())

    assert response.status_code == 401


def test_create_vehicle_links_to_current_user(client: TestClient) -> None:
    response = client.post(
        "/api/v1/vehicles",
        json=vehicle_payload(),
        headers=auth_headers(client),
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["plate"] == "ABC1D23"
    assert data["relationship_type"] == "owner"
    assert data["verification_status"] == "pending"


def test_list_vehicles_returns_current_user_links(client: TestClient) -> None:
    headers = auth_headers(client)
    client.post("/api/v1/vehicles", json=vehicle_payload(), headers=headers)

    response = client.get("/api/v1/vehicles", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["plate"] == "ABC1D23"


def test_get_vehicle_requires_link(client: TestClient) -> None:
    headers = auth_headers(client)
    created = client.post("/api/v1/vehicles", json=vehicle_payload(), headers=headers)
    vehicle_id = created.json()["id"]

    register_user(client, email="other@example.com", cpf="11122233344")
    other_token = login(client, email="other@example.com")
    response = client.get(
        f"/api/v1/vehicles/{vehicle_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


def test_duplicate_plate_returns_conflict(client: TestClient) -> None:
    headers = auth_headers(client)
    client.post("/api/v1/vehicles", json=vehicle_payload(), headers=headers)

    response = client.post(
        "/api/v1/vehicles",
        json=vehicle_payload(chassis="9BWZZZ377VT004252", renavam="98765432100"),
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Vehicle plate already registered"


def test_duplicate_chassis_returns_conflict(client: TestClient) -> None:
    headers = auth_headers(client)
    client.post("/api/v1/vehicles", json=vehicle_payload(), headers=headers)

    response = client.post(
        "/api/v1/vehicles",
        json=vehicle_payload(plate="DEF2E34", renavam="98765432100"),
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Vehicle chassis already registered"


def test_duplicate_renavam_returns_conflict(client: TestClient) -> None:
    headers = auth_headers(client)
    client.post("/api/v1/vehicles", json=vehicle_payload(), headers=headers)

    response = client.post(
        "/api/v1/vehicles",
        json=vehicle_payload(plate="DEF2E34", chassis="9BWZZZ377VT004252"),
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Vehicle Renavam already registered"
