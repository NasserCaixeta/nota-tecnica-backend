import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_auth_users import login, register_user, user_payload


def test_customer_registration_starts_pending(client: TestClient) -> None:
    body = register_user(client)
    assert body.get("participation_status") == "pending"
    assert body.get("is_admin") is False
    assert body.get("capabilities") == []
    token = login(client)
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["participation_status"] == "pending"


@pytest.mark.parametrize(
    "privilege",
    [{"is_admin": True}, {"participation_status": "approved"}, {"capabilities": ["admin"]}],
)
def test_public_registration_cannot_set_privileges(client: TestClient, privilege: dict) -> None:
    response = client.post("/api/v1/auth/register", json={**user_payload(), **privilege})
    assert response.status_code == 422


def test_workshop_registration_is_not_approved_representation(client: TestClient) -> None:
    body = register_user(client, profile_type="workshop_owner")
    assert body.get("capabilities") == []
    assert body.get("participation_status") == "pending"


async def test_audit_rolls_back_with_business_transaction(db_session: AsyncSession) -> None:
    from sqlalchemy import func, select

    from app.modules.audit.models import AuditEvent
    from app.modules.audit.service import append_audit

    await append_audit(
        db_session,
        actor_id=None,
        action="test",
        target_type="user",
        target_id=1,
        version=1,
        reason="Review",
        metadata={},
    )
    await db_session.rollback()
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0
