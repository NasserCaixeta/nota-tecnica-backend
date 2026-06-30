from fastapi.testclient import TestClient

from tests.test_maintenance import auth_headers, create_vehicle, maintenance_payload


def test_unknown_plate_returns_not_found_preview(client: TestClient) -> None:
    response = client.get("/api/v1/public/vehicles/ABC1D23/history-preview")

    assert response.status_code == 200
    assert response.json()["vehicle_found"] is False
    assert response.json()["maintenance_count"] == 0


def test_existing_plate_without_maintenance_returns_empty_preview(client: TestClient) -> None:
    headers = auth_headers(client)
    create_vehicle(client, headers)

    response = client.get("/api/v1/public/vehicles/ABC1D23/history-preview")

    assert response.status_code == 200
    assert response.json()["vehicle_found"] is True
    assert response.json()["maintenance_count"] == 0
    assert response.json()["completeness_score"] == "none"


def test_preview_returns_only_safe_aggregates(client: TestClient) -> None:
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    client.post(
        f"/api/v1/vehicles/{vehicle_id}/maintenance-records",
        json=maintenance_payload(),
        headers=headers,
    )

    response = client.get("/api/v1/public/vehicles/ABC1D23/history-preview")

    assert response.status_code == 200
    data = response.json()
    assert data["vehicle_found"] is True
    assert data["maintenance_count"] == 1
    assert data["categories"] == ["mechanical"]
    assert "cpf" not in data
    assert "documents" not in data
    assert "storage_key" not in data
    assert "description" not in data
