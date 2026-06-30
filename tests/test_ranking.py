from fastapi.testclient import TestClient

from tests.test_maintenance import auth_headers, create_vehicle, maintenance_payload
from tests.test_workshops import workshop_payload


def create_workshop(client: TestClient, headers: dict[str, str]) -> int:
    response = client.post("/api/v1/workshops", json=workshop_payload(), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_completed_workshop_maintenance_appears_in_ranking(client: TestClient) -> None:
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    workshop_id = create_workshop(client, headers)
    client.post(
        f"/api/v1/vehicles/{vehicle_id}/maintenance-records",
        json=maintenance_payload(workshop_id=workshop_id),
        headers=headers,
    )

    response = client.get("/api/v1/public/workshops/ranking")

    assert response.status_code == 200
    data = response.json()
    assert data["score_version"] == "initial_v1"
    assert data["items"][0]["workshop_id"] == workshop_id
    assert data["items"][0]["completed_services_count"] == 1


def test_draft_maintenance_does_not_enter_ranking(client: TestClient) -> None:
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    workshop_id = create_workshop(client, headers)
    client.post(
        f"/api/v1/vehicles/{vehicle_id}/maintenance-records",
        json=maintenance_payload(workshop_id=workshop_id, status="draft"),
        headers=headers,
    )

    response = client.get("/api/v1/public/workshops/ranking")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_ranking_filters_by_category(client: TestClient) -> None:
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    workshop_id = create_workshop(client, headers)
    client.post(
        f"/api/v1/vehicles/{vehicle_id}/maintenance-records",
        json=maintenance_payload(workshop_id=workshop_id, category="mechanical"),
        headers=headers,
    )

    response = client.get("/api/v1/public/workshops/ranking?category=electrical")

    assert response.status_code == 200
    assert response.json()["items"] == []
