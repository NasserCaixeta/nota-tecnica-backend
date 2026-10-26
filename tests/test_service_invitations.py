from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from tests.test_auth_users import login, register_user
from tests.test_maintenance import auth_headers, create_vehicle, maintenance_payload
from tests.test_maintenance_moderation import activate_link, approve_workshop_for_test


@pytest.fixture(autouse=True)
def invitation_settings(monkeypatch):
    monkeypatch.setenv("INVITATION_SECRET_KEY", "test-invitation-key-with-at-least-32-characters")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def workshop_service(client):
    office_headers = auth_headers(client)
    workshop_id = approve_workshop_for_test(client, office_headers)
    r = client.post(
        f"/api/v1/workshops/{workshop_id}/maintenance-records",
        headers=office_headers,
        json={**maintenance_payload(), "plate": "ABC1D23"},
    )
    assert r.status_code == 201, r.text
    return office_headers, r.json()


def issue_invitation(client, headers, record, email="other@example.com"):
    r = client.post(
        f"/api/v1/maintenance-records/{record['id']}/invitations",
        headers=headers,
        json={"revision_id": record["current_revision_id"], "recipient_email": email},
    )
    assert r.status_code == 201, r.text
    return r.json()


def accept(client, invitation, headers):
    return client.post(
        "/api/v1/service-invitations/accept", headers=headers, json={"token": invitation["token"]}
    )


def test_invitation_is_seven_days_and_does_not_bypass_approval_or_vehicle_validation(client):
    h, record = workshop_service(client)
    invitation = issue_invitation(client, h, record)
    assert (
        datetime.fromisoformat(invitation["expires_at"])
        - datetime.fromisoformat(invitation["created_at"])
    ) == timedelta(days=7)
    assert "ABC1D23" not in invitation["url"]
    assert "#" in invitation["url"]
    register_user(client, email="other@example.com", cpf="39053344705")
    customer = {"Authorization": f"Bearer {login(client, email='other@example.com')}"}
    pending = accept(client, invitation, customer)
    assert pending.status_code == 200
    assert pending.json() == {"state": "participation_pending"}
    from app.modules.users.models import ParticipationStatus, User

    async def approve():
        s = client.app.state.test_db_session
        user = await s.scalar(select(User).where(User.email == "other@example.com"))
        user.participation_status = ParticipationStatus.APPROVED
        await s.commit()

    client.portal.call(approve)
    assert accept(client, invitation, customer).json() == {"state": "relationship_required"}
    assert (
        client.get(f"/api/v1/maintenance-records/{record['id']}", headers=customer).status_code
        == 404
    )
    v = create_vehicle(client, customer)
    activate_link(client, v, "other@example.com")
    accepted = accept(client, invitation, customer)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["state"] == "awaiting_confirmation"
    detail = client.get(f"/api/v1/maintenance-records/{record['id']}", headers=customer).json()
    assert detail["customer_acknowledgement"] == "awaiting_customer"
    confirmed = client.post(
        f"/api/v1/maintenance-records/{record['id']}/acknowledge",
        headers=customer,
        json={"revision_id": record["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["customer_acknowledgement"] == "confirmed"
    assert accept(client, invitation, customer).status_code == 410


def test_wrong_recipient_and_reissued_or_expired_invitation_do_not_associate(client):
    h, record = workshop_service(client)
    old = issue_invitation(client, h, record)
    assert accept(client, old, h).status_code == 404
    new = issue_invitation(client, h, record)
    customer = auth_headers(client, email="other@example.com", cpf="39053344705")
    assert accept(client, old, customer).status_code == 410

    async def expire():
        from app.modules.maintenance.models import ServiceInvitation

        s = client.app.state.test_db_session
        item = await s.get(ServiceInvitation, new["id"])
        item.expires_at = item.created_at - timedelta(seconds=1)
        await s.commit()

    client.portal.call(expire)
    assert accept(client, new, customer).status_code == 410


def test_invitation_validation_does_not_create_a_garage_slot(client):
    from tests.test_vehicles import vehicle_payload

    h, record = workshop_service(client)
    invitation = issue_invitation(client, h, record)
    customer = auth_headers(client, email="other@example.com", cpf="39053344705")
    r = client.post(
        "/api/v1/service-invitations/relationship",
        headers=customer,
        json={"token": invitation["token"], "vehicle": vehicle_payload()},
    )
    assert r.status_code == 201, r.text
    assert r.json()["vehicle_id"] == record["vehicle_id"]
    assert client.get("/api/v1/garage", headers=customer).json()["vehicles"] == []
    assert accept(client, invitation, customer).json()["state"] == "relationship_required"
