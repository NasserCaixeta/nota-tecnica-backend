from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import NotificationRead
from app.modules.users.models import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


async def notification_read(session, notification):
    from app.modules.payments.models import HistoryAccessGrant
    from app.modules.vehicles.models import Vehicle, VehicleUser

    result = NotificationRead.model_validate(notification)
    target_type, target_id = notification.target_type, notification.target_id
    if target_type == "document":
        from app.modules.documents.models import Document

        document = await session.get(Document, target_id)
        if document:
            if document.maintenance_record_id:
                result.link = f"/app/manutencoes/{document.maintenance_record_id}"
            elif document.vehicle_id:
                result.link = f"/app/garagem/{document.vehicle_id}"
            elif document.workshop_claim_id:
                result.link = "/app/oficinas/reivindicar"
    elif target_type == "user":
        result.link = "/app/participacao"
    elif target_type == "vehicle_link":
        link = await session.get(VehicleUser, target_id)
        if link:
            result.link = f"/app/garagem/{link.vehicle_id}"
    elif target_type == "workshop_claim":
        result.link = (
            "/admin/oficinas"
            if notification.kind == "workshop_pending"
            else "/app/oficinas/reivindicar"
        )
    elif target_type == "maintenance_record":
        result.link = f"/app/manutencoes/{target_id}"
    elif target_type == "history_access_grant":
        grant = await session.get(HistoryAccessGrant, target_id)
        vehicle = await session.get(Vehicle, grant.vehicle_id) if grant else None
        if vehicle:
            result.link = f"/app/historico/{vehicle.plate}"
    elif target_type in {"subscription_period", "user_subscription"}:
        result.link = "/app/assinatura"
    return result


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    notifications = (
        await session.scalars(
            select(Notification)
            .where(Notification.recipient_id == user.id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(100)
        )
    ).all()
    return [await notification_read(session, notification) for notification in notifications]


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_read(
    notification_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    notification = await session.scalar(
        select(Notification)
        .where(Notification.id == notification_id, Notification.recipient_id == user.id)
        .with_for_update()
    )
    if notification is None:
        raise HTTPException(404, "Notification not found")
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
    await session.commit()
    return await notification_read(session, notification)
