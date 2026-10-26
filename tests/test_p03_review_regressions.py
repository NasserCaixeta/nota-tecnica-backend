import pytest
from sqlalchemy import select

from app.core.config import get_settings
from tests.test_documents import create_uploaded_document
from tests.test_maintenance import auth_headers, create_vehicle
from tests.test_maintenance_moderation import activate_link
from tests.test_service_invitations import accept, issue_invitation, workshop_service


@pytest.fixture(autouse=True)
def configure_invitations(monkeypatch):
    monkeypatch.setenv("INVITATION_SECRET_KEY", "test-invitation-key-with-at-least-32-characters")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def assigned_service(client):
    h, r = workshop_service(client)
    inv = issue_invitation(client, h, r)
    customer = auth_headers(client, email="other@example.com", cpf="39053344705")
    vehicle = create_vehicle(client, customer)
    activate_link(client, vehicle, "other@example.com")
    response = accept(client, inv, customer)
    assert response.status_code == 200, response.text
    return h, r, customer, vehicle


def test_confirmed_draft_evidence_change(client):
    h, r, customer, vehicle = assigned_service(client)
    old = create_uploaded_document(
        client, vehicle, h, maintenance_record_id=r["id"], document_type="invoice"
    )
    ack = client.post(
        f"/api/v1/maintenance-records/{r['id']}/acknowledge",
        headers=customer,
        json={"revision_id": r["current_revision_id"]},
    )
    assert ack.status_code == 200, ack.text
    new = create_uploaded_document(
        client, vehicle, h, maintenance_record_id=r["id"], document_type="invoice"
    )
    detail = client.get(f"/api/v1/maintenance-records/{r['id']}", headers=h).json()
    assert detail["current_revision_id"] != r["current_revision_id"]
    assert detail["customer_acknowledgement"] == "awaiting_customer"
    assert detail["customer_user_id"] is not None
    assert new["maintenance_revision_id"] != old["maintenance_revision_id"]


def test_pending_services_after_relationship_revoked(client):
    h, r, customer, vehicle = assigned_service(client)

    async def revoke():
        from app.modules.users.models import User
        from app.modules.vehicles.models import (
            GarageValidationStatus,
            VehicleUser,
            VerificationStatus,
        )

        s = client.app.state.test_db_session
        link = await s.scalar(
            select(VehicleUser)
            .join(User)
            .where(User.email == "other@example.com", VehicleUser.vehicle_id == vehicle)
        )
        link.verification_status = VerificationStatus.REJECTED
        link.garage_status = GarageValidationStatus.REJECTED
        await s.commit()

    client.portal.call(revoke)
    detail = client.get(f"/api/v1/maintenance-records/{r['id']}", headers=customer)
    pending = client.get("/api/v1/customer-services/pending", headers=customer)
    assert detail.status_code == 403
    assert pending.json() == [], "Private workshop data still returned after link revoked"


async def test_other_linked_owner_gets_only_reviewed_description(client, db_session, monkeypatch):
    import tests.test_maintenance_moderation as moderation

    original = moderation.create_record

    def sensitive_record(*args, **kwargs):
        kwargs["description"] = "Troca de óleo. Cliente Maria, contato privado 11912345678"
        return original(*args, **kwargs)

    monkeypatch.setattr(moderation, "create_record", sensitive_record)
    h, vehicle, r, _, _, _ = await moderation.approve_customer_service(client, db_session)
    other = auth_headers(client, email="other@example.com", cpf="39053344705")
    create_vehicle(client, other)
    activate_link(client, vehicle, "other@example.com")
    listed = client.get(f"/api/v1/vehicles/{vehicle}/maintenance-records", headers=other)
    detail = client.get(f"/api/v1/maintenance-records/{r['id']}", headers=other)
    assert listed.status_code == detail.status_code == 200
    assert "11912345678" not in listed.text and "11912345678" not in detail.text


async def test_unrelated_history_reader_receives_only_public_fields(client, db_session):
    from tests.test_maintenance_moderation import approve_customer_service

    _, vehicle, record, _, _, _ = await approve_customer_service(client, db_session)
    other = auth_headers(client, email="other@example.com", cpf="39053344705")
    create_vehicle(client, other)
    activate_link(client, vehicle, "other@example.com")
    forbidden = {
        "author_user_id",
        "customer_user_id",
        "review_reason",
        "review_version",
        "documents",
        "description",
        "permissions",
        "vehicle_id",
    }
    for url in (
        f"/api/v1/vehicles/{vehicle}/maintenance-records",
        f"/api/v1/maintenance-records/{record['id']}",
    ):
        response = client.get(url, headers=other)
        assert response.status_code == 200
        data = response.json()
        if isinstance(data, list):
            data = data[0]
        assert forbidden.isdisjoint(data)
        assert data["visibility"] == "published"
        assert data["public_description"] == "Troca de óleo e filtros"


def test_confirming_upload_after_customer_acknowledgement_requires_new_recognition(client):
    from tests.test_documents import create_upload_intent

    h, record, customer, vehicle = assigned_service(client)
    pending = create_upload_intent(
        client, vehicle, h, maintenance_record_id=record["id"], document_type="invoice"
    )
    ack = client.post(
        f"/api/v1/maintenance-records/{record['id']}/acknowledge",
        headers=customer,
        json={"revision_id": record["current_revision_id"]},
    )
    assert ack.status_code == 200
    # File bytes are accepted only now, after the customer's previous acknowledgement.
    uploaded = client.post(f"/api/v1/documents/{pending['id']}/confirm-upload", headers=h, json={})
    assert uploaded.status_code == 200
    current = client.get(f"/api/v1/maintenance-records/{record['id']}", headers=h).json()
    assert current["current_revision_id"] != record["current_revision_id"]
    assert current["customer_acknowledgement"] == "awaiting_customer"
    assert uploaded.json()["maintenance_revision_id"] == current["current_revision_id"]


def test_submit_permission_uses_service_evidence_and_not_the_current_senders_file_list(client):
    from app.modules.users.models import User
    from app.modules.vehicles.models import VerificationStatus
    from app.modules.workshops.models import WorkshopUser, WorkshopUserRole

    h, record = workshop_service(client)
    url = f"/api/v1/maintenance-records/{record['id']}"
    assert client.get(url, headers=h).json()["permissions"]["can_submit"] is False
    create_uploaded_document(
        client, record["vehicle_id"], h, maintenance_record_id=record["id"], document_type="invoice"
    )
    other = auth_headers(client, email="other@example.com", cpf="39053344705")

    async def add_responsible():
        session = client.app.state.test_db_session
        user = await session.scalar(select(User).where(User.email == "other@example.com"))
        session.add(
            WorkshopUser(
                user_id=user.id,
                workshop_id=record["workshop_id"],
                role=WorkshopUserRole.OWNER,
                verification_status=VerificationStatus.VERIFIED,
            )
        )
        await session.commit()

    client.portal.call(add_responsible)
    assert client.get(url + "/documents", headers=other).json() == []
    assert client.get(url, headers=other).json()["permissions"]["can_submit"] is True
