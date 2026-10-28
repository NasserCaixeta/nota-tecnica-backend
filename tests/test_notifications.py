from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.modules.users.models import User
from tests.test_maintenance import auth_headers


class MailCapture:
    def __init__(self, fail=False):
        self.fail = fail
        self.messages = []

    async def send(self, *, recipient, subject, text, message_id):
        from app.integrations.email.smtp import EmailDeliveryUnavailable

        if self.fail:
            raise EmailDeliveryUnavailable()
        self.messages.append(
            {"recipient": recipient, "subject": subject, "text": text, "message_id": message_id}
        )


async def test_notification_dedupe_and_rollback_are_transactional(client, db_session):
    from app.modules.notifications.models import Notification
    from app.modules.notifications.service import enqueue_notification

    auth_headers(client)
    user = await db_session.scalar(select(User))
    kwargs = dict(
        recipient_id=user.id,
        kind="participation_updated",
        target_type="user",
        target_id=user.id,
        dedupe_key="decision:1",
    )
    first = await enqueue_notification(db_session, **kwargs)
    second = await enqueue_notification(db_session, **kwargs)
    assert first.id == second.id
    assert await db_session.scalar(select(func.count()).select_from(Notification)) == 1
    await db_session.rollback()
    assert await db_session.scalar(select(func.count()).select_from(Notification)) == 0


async def test_only_recipient_can_list_or_mark_notification_read(client, db_session):
    from app.modules.notifications.service import enqueue_notification

    owner = auth_headers(client)
    user = await db_session.scalar(select(User).where(User.email == "driver@example.com"))
    notification = await enqueue_notification(
        db_session,
        recipient_id=user.id,
        kind="participation_updated",
        target_type="user",
        target_id=user.id,
        dedupe_key="decision:1",
    )
    await db_session.commit()
    other = auth_headers(client, email="other@example.com", cpf="39053344705")
    assert client.get("/api/v1/notifications", headers=other).json() == []
    assert (
        client.post(f"/api/v1/notifications/{notification.id}/read", headers=other).status_code
        == 404
    )
    listed = client.get("/api/v1/notifications", headers=owner)
    assert listed.status_code == 200
    assert listed.json()[0]["read_at"] is None
    assert "cpf" not in listed.text and "recipient_email" not in listed.text
    assert (
        client.post(f"/api/v1/notifications/{notification.id}/read", headers=owner).json()[
            "read_at"
        ]
        is not None
    )


async def invitation_delivery(client, session, monkeypatch):
    from app.modules.notifications.models import NotificationDelivery
    from tests.test_service_invitations import issue_invitation, workshop_service

    monkeypatch.setenv("INVITATION_SECRET_KEY", "test-invitation-key-with-at-least-32-characters")
    get_settings.cache_clear()
    office, record = workshop_service(client)
    invitation = issue_invitation(client, office, record)
    delivery = await session.scalar(select(NotificationDelivery))
    assert delivery is not None
    return office, record, invitation, delivery


async def test_smtp_failure_keeps_invitation_and_one_recoverable_delivery(
    client, db_session, monkeypatch
):
    from app.modules.maintenance.models import ServiceInvitation
    from app.modules.notifications.delivery import (
        pending_delivery_ids,
        process_notification_delivery,
    )
    from app.modules.notifications.models import Notification, NotificationDelivery

    _, _, invitation, delivery = await invitation_delivery(client, db_session, monkeypatch)
    sender = MailCapture(fail=True)
    now = datetime.now(UTC)
    await process_notification_delivery(db_session, delivery.id, sender, now)
    assert await db_session.get(ServiceInvitation, invitation["id"]) is not None
    assert delivery.status == "pending"
    assert delivery.id in await pending_delivery_ids(db_session, now + timedelta(hours=1))
    sender.fail = False
    await process_notification_delivery(db_session, delivery.id, sender, now + timedelta(minutes=6))
    await process_notification_delivery(db_session, delivery.id, sender, now + timedelta(minutes=7))
    assert len(sender.messages) == 1
    assert await db_session.scalar(select(func.count()).select_from(NotificationDelivery)) == 1
    assert delivery.status == "sent"
    assert sender.messages[0]["recipient"] == "other@example.com"
    assert invitation["url"] in sender.messages[0]["text"]
    assert sender.messages[0]["text"].count(invitation["token"]) == 1
    notification = await db_session.get(Notification, delivery.notification_id)
    assert invitation["token"] not in notification.body
    assert "52998224725" not in sender.messages[0]["text"]


async def test_replaced_invitation_is_not_emailed(client, db_session, monkeypatch):
    from app.modules.notifications.delivery import process_notification_delivery
    from tests.test_service_invitations import issue_invitation

    office, record, _, delivery = await invitation_delivery(client, db_session, monkeypatch)
    issue_invitation(client, office, record)
    sender = MailCapture()
    await process_notification_delivery(db_session, delivery.id, sender, datetime.now(UTC))
    assert sender.messages == []
    assert delivery.status == "cancelled"


async def test_participation_decision_creates_its_notification(client, db_session):
    from tests.test_auth_users import login, register_user
    from tests.test_participation_admin import admin_headers

    participant = register_user(client)
    admin = await admin_headers(client, db_session)
    response = client.patch(
        f"/api/v1/admin/participants/{participant['id']}/review",
        headers=admin,
        json={"decision": "approved", "expected_version": 1, "reason": "Conferido"},
    )
    assert response.status_code == 200
    own = {"Authorization": f"Bearer {login(client)}"}
    notifications = client.get("/api/v1/notifications", headers=own)
    assert notifications.status_code == 200
    assert any(item["kind"] == "participation_updated" for item in notifications.json())


async def test_broker_failure_after_commit_does_not_lose_delivery(client, db_session, monkeypatch):
    from app.modules.maintenance.models import ServiceInvitation
    from app.modules.notifications import service
    from app.modules.notifications.delivery import (
        pending_delivery_ids,
        process_notification_delivery,
    )

    monkeypatch.setenv("SMTP_ENABLED", "true")
    get_settings.cache_clear()
    dispatched = []

    def unavailable(delivery_id):
        dispatched.append(delivery_id)
        raise RuntimeError("Redis unavailable")

    monkeypatch.setattr(service, "dispatch_delivery", unavailable)
    _, _, invitation, delivery = await invitation_delivery(client, db_session, monkeypatch)
    assert dispatched == [delivery.id]
    assert await db_session.get(ServiceInvitation, invitation["id"]) is not None
    assert delivery.id in await pending_delivery_ids(db_session)
    sender = MailCapture()
    await process_notification_delivery(db_session, delivery.id, sender, datetime.now(UTC))
    assert len(sender.messages) == 1


async def test_email_dispatch_happens_only_after_outer_commit(client, db_session, monkeypatch):
    from app.modules.notifications import service

    auth_headers(client)
    user = await db_session.scalar(select(User))
    monkeypatch.setenv("SMTP_ENABLED", "true")
    get_settings.cache_clear()
    dispatched = []
    monkeypatch.setattr(service, "dispatch_delivery", dispatched.append)
    args = dict(
        recipient_id=user.id,
        kind="service_invitation",
        target_type="service_invitation",
        target_id=999,
    )
    await service.enqueue_notification(db_session, **args, dedupe_key="to-rollback")
    assert dispatched == []
    await db_session.rollback()
    assert dispatched == []
    await service.enqueue_notification(db_session, **args, dedupe_key="to-commit")
    assert dispatched == []
    await db_session.commit()
    assert len(dispatched) == 1 and isinstance(dispatched[0], int)


async def test_local_capture_mode_refuses_external_smtp(monkeypatch):
    from app.integrations.email.smtp import EmailDeliveryUnavailable, SMTPEmailSender

    monkeypatch.setenv("SMTP_ENABLED", "true")
    monkeypatch.setenv("SMTP_CAPTURE_ONLY", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp.external.example")
    get_settings.cache_clear()
    with pytest.raises(EmailDeliveryUnavailable):
        await SMTPEmailSender().send(
            recipient="other@example.com",
            subject="Test",
            text="Test",
            message_id="test@pilot.local",
        )
    get_settings.cache_clear()
