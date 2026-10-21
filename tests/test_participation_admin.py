import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.modules.audit.models import AuditEvent
from app.modules.users.models import User
from tests.test_admin_validation import create_admin_user
from tests.test_auth_users import login, register_user
from tests.test_vehicles import vehicle_payload


async def admin_headers(client, db_session):
    await create_admin_user(db_session)
    return {"Authorization": f"Bearer {login(client, 'admin@example.com')}"}


@pytest.mark.parametrize("path", ["/garage", "/vehicles", "/workshops/me"])
def test_pending_account_cannot_operate_with_valid_token(client: TestClient, path) -> None:
    register_user(client)
    response = client.get(f"/api/v1{path}", headers={"Authorization": f"Bearer {login(client)}"})
    assert response.status_code == 403


async def test_admin_approval_unlocks_operations_and_is_audited(client, db_session) -> None:
    user = register_user(client)
    token = login(client)
    admin = await admin_headers(client, db_session)
    response = client.patch(
        f"/api/v1/admin/participants/{user['id']}/review",
        headers=admin,
        json={"decision": "approved", "expected_version": 1, "reason": "Pilot participant"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["participation_version"] == 2
    headers = {"Authorization": f"Bearer {token}"}
    assert (
        client.post("/api/v1/vehicles", headers=headers, json=vehicle_payload()).status_code == 201
    )
    events = (await db_session.scalars(select(AuditEvent))).all()
    assert len(events) == 1
    assert events[0].target_id == user["id"]
    assert events[0].actor_id != user["id"]
    stale = client.patch(
        f"/api/v1/admin/participants/{user['id']}/review",
        headers=admin,
        json={"decision": "rejected", "expected_version": 1, "reason": "Stale decision"},
    )
    assert stale.status_code == 409
    assert len((await db_session.scalars(select(AuditEvent))).all()) == 1


async def test_admin_cannot_review_own_participation(client, db_session) -> None:
    headers = await admin_headers(client, db_session)
    admin = await db_session.scalar(select(User).where(User.email == "admin@example.com"))
    response = client.patch(
        f"/api/v1/admin/participants/{admin.id}/review",
        headers=headers,
        json={"decision": "approved", "expected_version": 1, "reason": "Own request"},
    )
    assert response.status_code == 409


async def test_last_administrator_cannot_be_removed(client, db_session) -> None:
    headers = await admin_headers(client, db_session)
    admin = await db_session.scalar(select(User).where(User.email == "admin@example.com"))
    response = client.patch(
        f"/api/v1/admin/users/{admin.id}/admin-access",
        headers=headers,
        json={"enabled": False, "reason": "Remove myself"},
    )
    assert response.status_code == 409


async def test_common_participant_cannot_review_or_grant_admin(client, db_session) -> None:
    user = register_user(client)
    headers = {"Authorization": f"Bearer {login(client)}"}
    response = client.patch(
        f"/api/v1/admin/users/{user['id']}/admin-access",
        headers=headers,
        json={"enabled": True, "reason": "Self promotion"},
    )
    assert response.status_code == 403
