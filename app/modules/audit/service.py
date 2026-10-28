from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditEvent


async def append_audit(
    session: AsyncSession,
    *,
    actor_id: int | None,
    action: str,
    target_type: str,
    target_id: int,
    version: int | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        version=version,
        reason=reason,
        event_metadata=metadata or {},
    )
    session.add(event)
    await session.flush()
    from app.modules.notifications.audit_notifications import notify_for_audit

    await notify_for_audit(session, event)
    return event
