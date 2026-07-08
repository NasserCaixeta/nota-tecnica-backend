from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_admin_validation import create_admin_user
from tests.test_auth_users import login
from tests.test_garage import upload_validation_document
from tests.test_maintenance import auth_headers
from tests.test_vehicles import vehicle_payload


async def admin_headers(client: TestClient, db_session: AsyncSession) -> dict[str, str]:
    await create_admin_user(db_session)
    token = login(client, email="admin@example.com")
    return {"Authorization": f"Bearer {token}"}


def submit_owner_vehicle_for_review(client: TestClient, headers: dict[str, str]) -> int:
    created = client.post(
        "/api/v1/garage/vehicles",
        json={**vehicle_payload(), "relationship_type": "owner"},
        headers=headers,
    )
    link_id = created.json()["vehicle_link_id"]
    upload_validation_document(client, link_id, headers, "crlv")
    submitted = client.post(
        f"/api/v1/garage/vehicle-links/{link_id}/submit-review",
        headers=headers,
    )
    assert submitted.status_code == 200
    return link_id


async def test_admin_lists_pending_garage_vehicle_links(
    client: TestClient,
    db_session: AsyncSession,
) -> None:
    user_headers = auth_headers(client)
    link_id = submit_owner_vehicle_for_review(client, user_headers)
    headers = await admin_headers(client, db_session)

    response = client.get("/api/v1/admin/garage/vehicle-links/pending", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()[0]["vehicle_link_id"] == link_id
    assert response.json()[0]["garage_status"] == "under_review"


async def test_admin_can_approve_garage_vehicle_link(
    client: TestClient,
    db_session: AsyncSession,
) -> None:
    user_headers = auth_headers(client)
    link_id = submit_owner_vehicle_for_review(client, user_headers)
    headers = await admin_headers(client, db_session)

    response = client.patch(
        f"/api/v1/admin/garage/vehicle-links/{link_id}/review",
        json={"verification_status": "verified"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["garage_status"] == "active"


async def test_admin_can_reject_garage_vehicle_link(
    client: TestClient,
    db_session: AsyncSession,
) -> None:
    user_headers = auth_headers(client)
    link_id = submit_owner_vehicle_for_review(client, user_headers)
    headers = await admin_headers(client, db_session)

    response = client.patch(
        f"/api/v1/admin/garage/vehicle-links/{link_id}/review",
        json={
            "verification_status": "rejected",
            "verification_rejection_reason": "Documento ilegível",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["garage_status"] == "rejected"
    assert response.json()["verification_rejection_reason"] == "Documento ilegível"
    assert response.json()["review_attempts"] == 1


async def test_admin_can_request_additional_documents(
    client: TestClient,
    db_session: AsyncSession,
) -> None:
    user_headers = auth_headers(client)
    link_id = submit_owner_vehicle_for_review(client, user_headers)
    headers = await admin_headers(client, db_session)

    response = client.post(
        f"/api/v1/admin/garage/vehicle-links/{link_id}/requested-documents",
        json={
            "requested_document_types": ["owner_authorization"],
            "note": "Enviar autorização assinada",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["garage_status"] == "pending_documents"
    assert "owner_authorization" in data["required_documents"]
    assert "owner_authorization" in data["missing_documents"]
