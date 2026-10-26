from fastapi.testclient import TestClient

from tests.test_maintenance import auth_headers, create_vehicle, maintenance_payload
from tests.test_maintenance_moderation import approve_customer_service
from tests.test_workshops import workshop_payload


def create_workshop(client: TestClient, headers: dict[str, str]) -> int:
    response = client.post("/api/v1/workshops", json=workshop_payload(), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_approved_workshop_maintenance_appears_in_ranking(
    client: TestClient, db_session
) -> None:
    headers = auth_headers(client)
    workshop_id = create_workshop(client, headers)
    from app.modules.vehicles.models import VerificationStatus
    from app.modules.workshops.models import Workshop

    office = await db_session.get(Workshop, workshop_id)
    office.verification_status = VerificationStatus.VERIFIED
    await db_session.commit()
    await approve_customer_service(client, db_session, workshop_id=workshop_id, headers=headers)

    response = client.get("/api/v1/public/workshops/ranking")

    assert response.status_code == 200
    data = response.json()
    assert data["score_version"] == "pilot_v1"
    assert data["items"] == []
    assert data["unranked_items"][0]["workshop_id"] == workshop_id
    assert data["unranked_items"][0]["completed_services_count"] == 1
    assert data["unranked_items"][0]["sample_label"] == "small_sample"


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
