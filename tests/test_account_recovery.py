import re
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from tests.test_auth_users import login, register_user
from tests.test_notifications import MailCapture


class RecoveryCounter:
    def __init__(self):
        self.counts = {}

    async def increment(self, key, window_seconds):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key], window_seconds


@pytest.fixture
def recovery_setup(client, monkeypatch):
    from app.core.rate_limit import get_rate_limit_backend

    monkeypatch.setenv("RECOVERY_SECRET_KEY", "recovery-key-separate-with-at-least-32-characters")
    get_settings.cache_clear()
    counter = RecoveryCounter()
    client.app.dependency_overrides[get_rate_limit_backend] = lambda: counter
    yield
    get_settings.cache_clear()


async def capture_recovery_token(session):
    from app.modules.notifications.delivery import process_notification_delivery
    from app.modules.notifications.models import NotificationDelivery

    sender = MailCapture()
    deliveries = list(
        await session.scalars(
            select(NotificationDelivery).where(NotificationDelivery.status == "pending")
        )
    )
    for delivery in deliveries:
        await process_notification_delivery(session, delivery.id, sender, datetime.now(UTC))
    assert len(sender.messages) == 1
    return re.search(r"/redefinir-senha#([^\s]+)", sender.messages[0]["text"]).group(1)


async def test_recovery_is_neutral_and_reset_invalidates_sessions_without_approval(
    client, db_session, recovery_setup
):
    from app.modules.auth.models import PasswordRecovery

    register_user(client)
    old_token = login(client)
    first = client.post("/api/v1/auth/forgot-password", json={"email": "driver@example.com"})
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.com"})
    assert first.status_code == unknown.status_code == 202
    assert first.json() == unknown.json()
    assert "token" not in first.text
    token = await capture_recovery_token(db_session)
    recovery = await db_session.scalar(select(PasswordRecovery))
    assert token != recovery.token_hash and token not in str(recovery.__dict__)
    assert recovery.expires_at - recovery.created_at == timedelta(minutes=60)
    response = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "new-strong-password"}
    )
    assert response.status_code == 200, response.text
    assert (
        client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {old_token}"}).status_code
        == 401
    )
    new_session = client.post(
        "/api/v1/auth/login",
        json={"email": "driver@example.com", "password": "new-strong-password"},
    )
    assert new_session.status_code == 200
    profile = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {new_session.json()['access_token']}"},
    )
    assert profile.json()["participation_status"] == "pending"
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "another-strong-password"},
        ).status_code
        == 400
    )


async def test_expired_and_replaced_recovery_tokens_are_rejected(
    client, db_session, recovery_setup
):
    from app.modules.auth.models import PasswordRecovery

    register_user(client)
    assert (
        client.post(
            "/api/v1/auth/forgot-password", json={"email": "driver@example.com"}
        ).status_code
        == 202
    )
    token = await capture_recovery_token(db_session)
    row = await db_session.scalar(select(PasswordRecovery))
    row.created_at = datetime.now(UTC) - timedelta(hours=2)
    row.expires_at = datetime.now(UTC) - timedelta(hours=1)
    await db_session.commit()
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "new-strong-password"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/auth/forgot-password", json={"email": "driver@example.com"}
        ).status_code
        == 202
    )
    fresh = await capture_recovery_token(db_session)
    assert fresh != token
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "new-strong-password"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": fresh, "new_password": "new-strong-password"},
        ).status_code
        == 200
    )


async def test_account_requests_are_private_and_do_not_delete_user(client, db_session):
    from app.modules.users.models import User
    from tests.test_maintenance import auth_headers
    from tests.test_participation_admin import admin_headers

    own = auth_headers(client)
    response = client.post(
        "/api/v1/users/me/closure-requests",
        headers=own,
        json={"reason": "Quero encerrar minha participação no piloto."},
    )
    assert response.status_code == 201, response.text
    request_id = response.json()["id"]
    assert (
        client.get("/api/v1/users/me/closure-requests", headers=own).json()[0]["id"] == request_id
    )
    other = auth_headers(client, email="other@example.com", cpf="39053344705")
    assert client.get("/api/v1/users/me/closure-requests", headers=other).json() == []
    assert client.get("/api/v1/admin/account-requests", headers=other).status_code == 403
    admin = await admin_headers(client, db_session)
    assert any(
        row["id"] == request_id
        for row in client.get("/api/v1/admin/account-requests", headers=admin).json()
    )
    assert (
        await db_session.scalar(select(User).where(User.email == "driver@example.com"))
    ).is_active is True
    assert client.patch("/api/v1/users/me", headers=own, json={"is_admin": True}).status_code == 422
    assert (
        client.patch("/api/v1/users/me", headers=own, json={"cpf": "11144477735"}).status_code
        == 422
    )


def test_recovery_limits_attempts_without_revealing_account_existence(client, recovery_setup):
    for _ in range(3):
        assert (
            client.post(
                "/api/v1/auth/forgot-password", json={"email": "missing@example.com"}
            ).status_code
            == 202
        )
    limited = client.post("/api/v1/auth/forgot-password", json={"email": "MISSING@example.com"})
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0


async def test_legacy_session_is_accepted_until_a_security_action(
    client, db_session, recovery_setup
):
    import jwt

    from app.modules.users.models import User

    register_user(client)
    user = await db_session.scalar(select(User))
    legacy = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(hours=1)},
        get_settings().jwt_secret_key,
        algorithm="HS256",
    )
    headers = {"Authorization": f"Bearer {legacy}"}
    assert client.get("/api/v1/users/me", headers=headers).status_code == 200
    client.post("/api/v1/auth/forgot-password", json={"email": "driver@example.com"})
    token = await capture_recovery_token(db_session)
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "new-strong-password"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/users/me", headers=headers).status_code == 401


def test_recovery_fails_closed_when_attempt_counter_is_unavailable(client, recovery_setup):
    from app.core.rate_limit import RateLimitUnavailable, get_rate_limit_backend

    class Unavailable:
        async def increment(self, *args):
            raise RateLimitUnavailable()

    client.app.dependency_overrides[get_rate_limit_backend] = lambda: Unavailable()
    response = client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.com"})
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "10"


async def test_identity_change_request_does_not_silently_replace_cpf(client, db_session):
    from app.modules.users.models import User
    from tests.test_maintenance import auth_headers

    headers = auth_headers(client)
    before = await db_session.scalar(select(User))
    original = before.cpf
    response = client.post(
        "/api/v1/users/me/identity-requests",
        headers=headers,
        json={"reason": "Solicito orientação para corrigir minha identificação."},
    )
    assert response.status_code == 201
    repeated = client.post(
        "/api/v1/users/me/identity-requests",
        headers=headers,
        json={"reason": "Solicito orientação para corrigir minha identificação."},
    )
    assert repeated.json()["id"] == response.json()["id"]
    assert (await db_session.scalar(select(User))).cpf == original


async def test_name_used_in_pending_workshop_analysis_requires_administrative_request(
    client, db_session
):
    from app.modules.users.models import User
    from app.modules.workshops.claims import create_workshop_claim
    from tests.test_maintenance import auth_headers
    from tests.test_workshops import workshop_payload

    headers = auth_headers(client)
    workshop = client.post("/api/v1/workshops", headers=headers, json=workshop_payload())
    user = await db_session.scalar(select(User))
    await create_workshop_claim(db_session, workshop.json()["id"], user)
    response = client.patch(
        "/api/v1/users/me", headers=headers, json={"full_name": "Outra identificação"}
    )
    assert response.status_code == 409
    assert (await db_session.scalar(select(User))).full_name == "Maria Driver"


def test_recovery_response_does_not_depend_on_account_specific_broker_dispatch(
    client, recovery_setup, monkeypatch
):
    from app.modules.notifications import service

    monkeypatch.setenv("SMTP_ENABLED", "true")
    get_settings.cache_clear()
    sent = []
    monkeypatch.setattr(service, "dispatch_delivery", sent.append)
    register_user(client)
    own = client.post("/api/v1/auth/forgot-password", json={"email": "driver@example.com"})
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.com"})
    assert own.status_code == unknown.status_code == 202
    assert sent == []  # Durable delivery is dispatched by periodic recovery after the response.
