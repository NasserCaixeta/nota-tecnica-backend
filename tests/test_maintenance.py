from fastapi.testclient import TestClient

from tests.test_auth_users import login, register_user
from tests.test_vehicles import vehicle_payload


def auth_headers(
    client: TestClient,
    *,
    email: str = "driver@example.com",
    cpf: str = "12345678901",
) -> dict[str, str]:
    register_user(client, email=email, cpf=cpf)
    token = login(client, email=email)
    return {"Authorization": f"Bearer {token}"}


def create_vehicle(client: TestClient, headers: dict[str, str], *, plate: str = "ABC1D23") -> int:
    response = client.post(
        "/api/v1/vehicles",
        json=vehicle_payload(plate=plate),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def maintenance_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "service_date": "2026-06-15",
        "odometer": 50000,
        "category": "mechanical",
        "vehicle_system": "engine",
        "description": "Oil and filter change",
        "labor_cost": "120.00",
        "parts_cost": "180.00",
        "warranty_months": 6,
        "entry_date": "2026-06-14",
        "promised_delivery_date": "2026-06-15",
        "actual_delivery_date": "2026-06-15",
        "status": "completed",
    }
    payload.update(overrides)
    return payload


def test_linked_user_can_create_maintenance_record(client: TestClient) -> None:
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)

    response = client.post(
        f"/api/v1/vehicles/{vehicle_id}/maintenance-records",
        json=maintenance_payload(),
        headers=headers,
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["vehicle_id"] == vehicle_id
    assert data["total_cost"] == "300.00"
    assert data["status"] == "completed"


def test_unlinked_user_cannot_create_maintenance_record(client: TestClient) -> None:
    owner_headers = auth_headers(client)
    vehicle_id = create_vehicle(client, owner_headers)
    other_headers = auth_headers(client, email="other@example.com", cpf="11122233344")

    response = client.post(
        f"/api/v1/vehicles/{vehicle_id}/maintenance-records",
        json=maintenance_payload(),
        headers=other_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Vehicle not found"


def test_list_and_read_maintenance_records(client: TestClient) -> None:
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    created = client.post(
        f"/api/v1/vehicles/{vehicle_id}/maintenance-records",
        json=maintenance_payload(),
        headers=headers,
    )
    record_id = created.json()["id"]

    list_response = client.get(
        f"/api/v1/vehicles/{vehicle_id}/maintenance-records",
        headers=headers,
    )
    read_response = client.get(
        f"/api/v1/maintenance-records/{record_id}",
        headers=headers,
    )

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert read_response.status_code == 200
    assert read_response.json()["id"] == record_id


def test_author_can_update_maintenance_record(client: TestClient) -> None:
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    created = client.post(
        f"/api/v1/vehicles/{vehicle_id}/maintenance-records",
        json=maintenance_payload(status="draft"),
        headers=headers,
    )
    record_id = created.json()["id"]

    response = client.patch(
        f"/api/v1/maintenance-records/{record_id}",
        json={"labor_cost": "200.00", "parts_cost": "100.00", "status": "completed"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["total_cost"] == "300.00"
    assert response.json()["status"] == "completed"
