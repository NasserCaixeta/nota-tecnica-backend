from datetime import UTC, datetime

from sqlalchemy import event, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.notifications.models import Notification, NotificationDelivery

MESSAGES = {
    "password_changed": (
        "Senha alterada",
        "As sessões anteriores foram encerradas. Entre novamente com sua nova senha.",
    ),
    "workshop_pending": (
        "Solicitação de oficina pendente",
        "Uma solicitação de representação aguarda análise administrativa.",
    ),
    "participation_updated": (
        "Participação analisada",
        "Confira a decisão e as orientações na sua conta.",
    ),
    "document_reviewed": (
        "Comprovante analisado",
        "Confira a análise e as orientações na área correspondente.",
    ),
    "vehicle_updated": (
        "Vínculo do veículo analisado",
        "Confira a situação do vínculo na garagem.",
    ),
    "documents_requested": (
        "Documentos adicionais solicitados",
        "Confira a lista de documentos na garagem.",
    ),
    "workshop_updated": (
        "Representação da oficina analisada",
        "Confira a decisão na área de oficinas.",
    ),
    "service_updated": ("Serviço atualizado", "Confira a versão e a situação atual do serviço."),
    "recognition_pending": (
        "Reconhecimento de serviço pendente",
        "Confira o serviço e confirme ou conteste a versão apresentada.",
    ),
    "dispute_updated": (
        "Contestação atualizada",
        "Confira as pendências e a decisão na área do serviço.",
    ),
    "benefit_updated": (
        "Benefício comercial atualizado",
        "Confira a validade e a situação do benefício na sua conta.",
    ),
    "service_invitation": (
        "Convite para reconhecer serviço",
        "Abra o link do convite enviado por e-mail para continuar.",
    ),
    "password_recovery": ("Recuperação de acesso", "Confira as instruções enviadas por e-mail."),
    "account_request": (
        "Solicitação de conta registrada",
        "Acompanhe a solicitação administrativa na sua conta.",
    ),
}


async def enqueue_notification(
    session: AsyncSession,
    *,
    recipient_id: int | None,
    kind: str,
    target_type: str,
    target_id: int,
    dedupe_key: str,
) -> Notification:
    if recipient_id is None and kind != "service_invitation":
        raise ValueError("An account is required for this notification")
    if kind not in MESSAGES:
        raise ValueError("Unknown notification kind")
    insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    title, body = MESSAGES[kind]
    # A single conflict-safe INSERT participates in the caller's transaction.
    # No nested SAVEPOINT: SQLite's legacy transaction mode may commit a first
    # SAVEPOINT independently, defeating an outer rollback.
    notification_id = await session.scalar(
        insert(Notification)
        .values(
            recipient_id=recipient_id,
            kind=kind,
            target_type=target_type,
            target_id=target_id,
            dedupe_key=dedupe_key,
            title=title,
            body=body,
            created_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(index_elements=[Notification.dedupe_key])
        .returning(Notification.id)
    )
    notification = await session.scalar(
        select(Notification).where(Notification.dedupe_key == dedupe_key)
    )
    if notification_id is None:
        return notification
    if kind in {"service_invitation", "password_recovery"}:
        delivery_id = await session.scalar(
            insert(NotificationDelivery)
            .values(
                notification_id=notification.id,
                channel="email",
                status="pending",
                attempts=0,
            )
            .on_conflict_do_nothing(
                index_elements=[NotificationDelivery.notification_id, NotificationDelivery.channel]
            )
            .returning(NotificationDelivery.id)
        )
        # Recovery uses periodic dispatch so response latency never depends on
        # an account-specific broker connection. The durable outbox is unchanged.
        if delivery_id is not None and kind != "password_recovery":
            session.info.setdefault("notification_delivery_ids", set()).add(delivery_id)
    return notification


def dispatch_delivery(delivery_id: int):
    from app.integrations.queue.notification_tasks import deliver_notification_task

    deliver_notification_task.delay(delivery_id)


@event.listens_for(Session, "after_commit")
def dispatch_after_commit(session):
    if session.in_nested_transaction():
        return
    ids = session.info.pop("notification_delivery_ids", set())
    if not get_settings().smtp_enabled:
        return
    for delivery_id in ids:
        try:
            dispatch_delivery(delivery_id)
        except Exception:
            # Periodic recovery reads the durable outbox after broker outages.
            pass


@event.listens_for(Session, "after_soft_rollback")
def discard_rolled_back_dispatch(session, previous_transaction):
    if previous_transaction.parent is None:
        session.info.pop("notification_delivery_ids", None)
