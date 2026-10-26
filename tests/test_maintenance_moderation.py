import pytest
from sqlalchemy import select

from tests.test_documents import create_uploaded_document
from tests.test_maintenance import auth_headers, create_vehicle, maintenance_payload
from tests.test_participation_admin import admin_headers


def activate_link(client, vehicle_id, email="driver@example.com"):
    async def activate():
        from app.modules.users.models import User
        from app.modules.vehicles.models import (
            GarageValidationStatus,
            VehicleUser,
            VerificationStatus,
        )

        session = client.app.state.test_db_session
        link = await session.scalar(
            select(VehicleUser)
            .join(User)
            .where(VehicleUser.vehicle_id == vehicle_id, User.email == email)
        )
        link.garage_status = GarageValidationStatus.ACTIVE
        link.verification_status = VerificationStatus.VERIFIED
        await session.commit()

    client.portal.call(activate)


def create_record(client, headers, vehicle_id, **overrides):
    r = client.post(
        f"/api/v1/vehicles/{vehicle_id}/maintenance-records",
        headers=headers,
        json=maintenance_payload(**overrides),
    )
    assert r.status_code == 201, r.text
    return r.json()


def submit(client, record, headers):
    return client.post(
        f"/api/v1/maintenance-records/{record['id']}/submit",
        headers=headers,
        json={"revision_id": record["current_revision_id"]},
    )


@pytest.mark.parametrize(
    "updates",
    [
        {"description": "   "},
        {"labor_cost": "-1.00"},
        {"entry_date": "2026-06-16", "actual_delivery_date": "2026-06-15"},
        {"entry_date": "2026-06-16", "promised_delivery_date": "2026-06-15"},
        {"admin_status": "approved"},
    ],
)
def test_invalid_service_data_is_rejected(client, updates):
    h = auth_headers(client)
    v = create_vehicle(client, h)
    r = client.post(
        f"/api/v1/vehicles/{v}/maintenance-records", headers=h, json=maintenance_payload(**updates)
    )
    assert r.status_code == 422


def test_legacy_completed_flag_does_not_publish_and_submission_requires_verified_evidence(client):
    h = auth_headers(client)
    v = create_vehicle(client, h)
    record = create_record(client, h, v)
    assert record["editorial_status"] == "draft"
    assert record["customer_acknowledgement"] == "author_acknowledged"
    assert (
        client.get("/api/v1/public/vehicles/ABC1D23/history-preview").json()["maintenance_count"]
        == 0
    )
    assert submit(client, record, h).status_code == 403
    activate_link(client, v)
    assert submit(client, record, h).status_code == 409


def test_cancelled_record_cannot_be_submitted(client):
    h = auth_headers(client)
    v = create_vehicle(client, h)
    activate_link(client, v)
    record = create_record(client, h, v, status="cancelled")
    create_uploaded_document(
        client, v, h, maintenance_record_id=record["id"], document_type="invoice"
    )
    assert record["editorial_status"] == "cancelled"
    assert submit(client, record, h).status_code == 409


async def approve_customer_service(client, db_session, *, workshop_id=None, headers=None):
    h = headers or auth_headers(client)
    v = create_vehicle(client, h)
    activate_link(client, v)
    record = create_record(client, h, v, workshop_id=workshop_id)
    doc = create_uploaded_document(
        client, v, h, maintenance_record_id=record["id"], document_type="invoice"
    )
    admin = await admin_headers(client, db_session)
    result = submit(client, record, h)
    assert result.status_code == 200, result.text
    early = client.patch(
        f"/api/v1/admin/maintenance-reviews/{record['id']}",
        headers=admin,
        json={
            "expected_version": result.json()["review_version"],
            "revision_id": record["current_revision_id"],
            "decision": "approved",
            "reason": "Checked",
            "public_description": "Troca de óleo e filtros",
        },
    )
    assert early.status_code == 409
    assert (
        client.patch(
            f"/api/v1/admin/documents/{doc['id']}/review",
            headers=admin,
            json={"expected_version": 1, "review_status": "approved"},
        ).status_code
        == 200
    )
    detail = client.get(f"/api/v1/admin/maintenance-reviews/{record['id']}", headers=admin).json()
    payload = {
        "expected_version": detail["review_version"],
        "revision_id": detail["current_revision_id"],
        "decision": "approved",
        "reason": "Document inspected",
        "public_description": "Troca de óleo e filtros",
    }
    approved = client.patch(
        f"/api/v1/admin/maintenance-reviews/{record['id']}", headers=admin, json=payload
    )
    assert approved.status_code == 200, approved.text
    return h, v, approved.json(), doc, admin, payload


async def test_customer_service_publishes_only_current_approved_revision(client, db_session):
    h, v, record, doc, admin, payload = await approve_customer_service(client, db_session)
    assert record["published"] is True
    assert (
        client.get("/api/v1/public/vehicles/ABC1D23/history-preview").json()["maintenance_count"]
        == 1
    )
    stale = client.patch(
        f"/api/v1/admin/maintenance-reviews/{record['id']}", headers=admin, json=payload
    )
    assert stale.status_code == 409
    # Relevant edits are new immutable data revisions and immediately remove publication.
    changed = client.patch(
        f"/api/v1/maintenance-records/{record['id']}",
        headers=h,
        json={"description": "Corrected oil specification"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["current_revision_id"] != record["current_revision_id"]
    assert changed.json()["admin_status"] == "pending"
    assert changed.json()["published"] is False
    assert (
        client.get("/api/v1/public/vehicles/ABC1D23/history-preview").json()["maintenance_count"]
        == 0
    )


async def test_document_rejection_immediately_removes_publication(client, db_session):
    h, v, record, doc, admin, _ = await approve_customer_service(client, db_session)
    r = client.patch(
        f"/api/v1/admin/documents/{doc['id']}/review",
        headers=admin,
        json={"expected_version": 2, "review_status": "rejected", "rejection_reason": "Invalid"},
    )
    assert r.status_code == 200
    assert (
        client.get("/api/v1/public/vehicles/ABC1D23/history-preview").json()["maintenance_count"]
        == 0
    )


def approve_workshop_for_test(client, headers):
    from tests.test_workshops import workshop_payload

    r = client.post("/api/v1/workshops", headers=headers, json=workshop_payload())
    assert r.status_code == 201
    office = r.json()

    async def approve():
        from app.modules.users.models import User
        from app.modules.vehicles.models import VerificationStatus
        from app.modules.workshops.models import Workshop, WorkshopUser, WorkshopUserRole

        session = client.app.state.test_db_session
        user = await session.scalar(select(User).where(User.email == "driver@example.com"))
        workshop = await session.get(Workshop, office["id"])
        workshop.verification_status = VerificationStatus.VERIFIED
        session.add(
            WorkshopUser(
                workshop_id=office["id"],
                user_id=user.id,
                role=WorkshopUserRole.OWNER,
                verification_status=VerificationStatus.VERIFIED,
            )
        )
        await session.commit()

    client.portal.call(approve)
    return office["id"]


def test_workshop_can_record_plate_without_personal_garage_and_not_publish(client):
    h = auth_headers(client)
    office = approve_workshop_for_test(client, h)
    r = client.post(
        f"/api/v1/workshops/{office}/maintenance-records",
        headers=h,
        json={**maintenance_payload(), "plate": "XYZ9A87"},
    )
    assert r.status_code == 201, r.text
    record = r.json()
    assert record["origin"] == "workshop"
    assert record["customer_acknowledgement"] == "awaiting_customer"
    assert record["published"] is False
    assert client.get("/api/v1/garage", headers=h).json()["vehicles"] == []
    proof = create_uploaded_document(
        client,
        record["vehicle_id"],
        h,
        maintenance_record_id=record["id"],
        document_type="service_order",
    )
    assert proof["maintenance_revision_id"] == record["current_revision_id"]
    assert submit(client, record, h).status_code == 200
    assert (
        client.get("/api/v1/public/vehicles/XYZ9A87/history-preview").json()["maintenance_count"]
        == 0
    )


def test_active_vehicle_link_does_not_expose_other_authors_private_drafts(client):
    h = auth_headers(client)
    office = approve_workshop_for_test(client, h)
    r = client.post(
        f"/api/v1/workshops/{office}/maintenance-records",
        headers=h,
        json={**maintenance_payload(), "plate": "ABC1D23"},
    )
    assert r.status_code == 201, r.text
    other = auth_headers(client, email="other@example.com", cpf="39053344705")
    v = create_vehicle(client, other)
    activate_link(client, v, "other@example.com")
    assert client.get(f"/api/v1/vehicles/{v}/maintenance-records", headers=other).json() == []
    assert (
        client.get(f"/api/v1/maintenance-records/{r.json()['id']}", headers=other).status_code
        == 404
    )


def test_service_detail_exposes_server_permissions_and_only_senders_documents(client):
    h = auth_headers(client)
    v = create_vehicle(client, h)
    record = create_record(client, h, v)
    detail = client.get(f"/api/v1/maintenance-records/{record['id']}", headers=h).json()
    assert detail["permissions"] == {
        "can_edit": True,
        "can_submit": False,
        "can_acknowledge": False,
        "can_dispute": False,
        "can_invite": False,
        "can_review": False,
    }
    proof = create_uploaded_document(
        client, v, h, maintenance_record_id=record["id"], document_type="invoice"
    )
    documents = client.get(f"/api/v1/maintenance-records/{record['id']}/documents", headers=h)
    assert documents.status_code == 200
    assert documents.json()[0]["id"] == proof["id"]
