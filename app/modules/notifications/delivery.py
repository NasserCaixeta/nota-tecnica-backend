from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.email.smtp import EmailDeliveryUnavailable
from app.modules.notifications.models import Notification, NotificationDelivery


class ObsoleteMessage(RuntimeError):
    pass


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def render_email(session, notification, now):
    if notification.kind == "service_invitation":
        from app.modules.maintenance.invitations import invitation_token, token_hash
        from app.modules.maintenance.models import MaintenanceRecord, ServiceInvitation

        invitation = await session.get(
            ServiceInvitation, notification.target_id, populate_existing=True
        )
        if (
            invitation is None
            or invitation.revoked_at is not None
            or invitation.consumed_at is not None
            or utc(invitation.expires_at) <= now
        ):
            raise ObsoleteMessage()
        record = await session.get(MaintenanceRecord, invitation.record_id, populate_existing=True)
        if (
            record is None
            or record.current_revision_id != invitation.revision_id
            or record.superseded_by_id
        ):
            raise ObsoleteMessage()
        token = invitation_token(invitation.nonce)
        if token_hash(token) != invitation.token_hash:
            raise ObsoleteMessage()
        link = f"{get_settings().frontend_url.rstrip('/')}/convite-servico#{token}"
        return (
            invitation.recipient_email,
            "Convite para reconhecer serviço — Nota Técnica",
            (
                f"Você recebeu um convite para conferir um serviço.\n\n{link}\n\n"
                "O convite é pessoal, expira em sete dias e exige aprovação e vínculo validado. "
                "Aceitar o convite não confirma o serviço."
            ),
        )
    if notification.kind == "password_recovery":
        from app.modules.auth.recovery import render_recovery_email

        return await render_recovery_email(session, notification.target_id, now)
    raise ObsoleteMessage()


async def pending_delivery_ids(session: AsyncSession, now: datetime | None = None):
    now = now or datetime.now(UTC)
    return list(
        (
            await session.scalars(
                select(NotificationDelivery.id)
                .where(
                    NotificationDelivery.status == "pending",
                    or_(
                        NotificationDelivery.next_attempt_at.is_(None),
                        NotificationDelivery.next_attempt_at <= now,
                    ),
                )
                .order_by(NotificationDelivery.id)
                .limit(100)
            )
        ).all()
    )


async def process_notification_delivery(
    session: AsyncSession, delivery_id: int, sender, now: datetime
):
    delivery = await session.scalar(
        select(NotificationDelivery)
        .where(NotificationDelivery.id == delivery_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if delivery is None or delivery.status != "pending":
        return
    delivery.attempts += 1
    notification = await session.get(Notification, delivery.notification_id)
    try:
        recipient, subject, text = await render_email(session, notification, now)
        await sender.send(
            recipient=recipient,
            subject=subject,
            text=text,
            message_id=f"nota-tecnica.delivery.{delivery.id}@pilot.local",
        )
    except ObsoleteMessage:
        delivery.status = "cancelled"
        delivery.last_error = "obsolete_message"
    except EmailDeliveryUnavailable:
        delivery.last_error = "smtp_unavailable"
        delivery.next_attempt_at = now + timedelta(minutes=min(60, 2 ** min(delivery.attempts, 6)))
    else:
        delivery.status = "sent"
        delivery.sent_at = now
        delivery.next_attempt_at = None
        delivery.last_error = None
    await session.commit()
