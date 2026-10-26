from tests.test_garage import upload_validation_document
from tests.test_maintenance import auth_headers
from tests.test_participation_admin import admin_headers
from tests.test_vehicles import vehicle_payload


async def prepare_review(client, db_session):
    owner = auth_headers(client)
    vehicle = client.post("/api/v1/garage/vehicles", json=vehicle_payload(), headers=owner).json()
    document = upload_validation_document(client, vehicle["vehicle_link_id"], owner, "crlv")
    client.post(
        f"/api/v1/garage/vehicle-links/{vehicle['vehicle_link_id']}/submit-review", headers=owner
    )
    admin = await admin_headers(client, db_session)
    return owner, vehicle, document, admin


async def test_uploaded_document_must_be_accepted_before_vehicle_activation(client, db_session):
    owner, vehicle, document, admin = await prepare_review(client, db_session)
    response = client.patch(
        f"/api/v1/admin/garage/vehicle-links/{vehicle['vehicle_link_id']}/review",
        headers=admin,
        json={"verification_status": "verified", "expected_version": 1},
    )
    assert response.status_code == 409
    own = client.get(f"/api/v1/garage/vehicles/{vehicle['vehicle_id']}", headers=owner).json()
    assert own["documents"]["awaiting_review"] == ["crlv"]
    assert own["documents"]["approved"] == []


async def test_legacy_verification_route_cannot_bypass_document_review(client, db_session):
    owner = auth_headers(client)
    vehicle = client.post("/api/v1/vehicles", json=vehicle_payload(), headers=owner).json()
    admin = await admin_headers(client, db_session)
    response = client.patch(
        f"/api/v1/admin/vehicle-links/{vehicle['vehicle_link_id']}/verification",
        headers=admin,
        json={"verification_status": "verified", "expected_version": 1},
    )
    assert response.status_code == 409


async def test_admin_can_review_evidence_then_approve_current_vehicle_version(client, db_session):
    owner, vehicle, document, admin = await prepare_review(client, db_session)
    accepted = client.patch(
        f"/api/v1/admin/documents/{document['id']}/review",
        headers=admin,
        json={"review_status": "approved", "expected_version": 1},
    )
    assert accepted.status_code == 200
    detail = client.get(
        f"/api/v1/admin/garage/vehicle-links/{vehicle['vehicle_link_id']}", headers=admin
    )
    assert detail.status_code == 200
    payload = {
        "verification_status": "verified",
        "expected_version": detail.json()["review_version"],
    }
    approved = client.patch(
        f"/api/v1/admin/garage/vehicle-links/{vehicle['vehicle_link_id']}/review",
        headers=admin,
        json=payload,
    )
    assert approved.status_code == 200
    assert approved.json()["garage_status"] == "active"
    stale = client.patch(
        f"/api/v1/admin/garage/vehicle-links/{vehicle['vehicle_link_id']}/review",
        headers=admin,
        json={
            **payload,
            "verification_status": "rejected",
            "verification_rejection_reason": "Stale decision",
        },
    )
    assert stale.status_code == 409


async def test_rejected_document_reopens_documentation_and_cannot_activate_link(client, db_session):
    owner, vehicle, document, admin = await prepare_review(client, db_session)
    rejected = client.patch(
        f"/api/v1/admin/documents/{document['id']}/review",
        headers=admin,
        json={"review_status": "rejected", "rejection_reason": "Illegible", "expected_version": 1},
    )
    assert rejected.status_code == 200
    own = client.get(f"/api/v1/garage/vehicles/{vehicle['vehicle_id']}", headers=owner).json()
    assert own["garage_status"] == "pending_documents"
    assert own["documents"]["rejected"] == ["crlv"]


async def test_administrator_cannot_approve_own_document(client, db_session):
    admin = await admin_headers(client, db_session)
    vehicle = client.post("/api/v1/garage/vehicles", json=vehicle_payload(), headers=admin).json()
    document = upload_validation_document(client, vehicle["vehicle_link_id"], admin, "crlv")
    response = client.patch(
        f"/api/v1/admin/documents/{document['id']}/review",
        headers=admin,
        json={"review_status": "approved", "expected_version": 1},
    )
    assert response.status_code == 409
