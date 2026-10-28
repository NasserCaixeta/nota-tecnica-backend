from sqlalchemy import select

from app.modules.notifications.service import enqueue_notification
from app.modules.users.models import ParticipationStatus, User


async def administrative_recipients(session):
    return set(
        (
            await session.scalars(
                select(User.id).where(
                    User.is_active.is_(True),
                    User.is_admin.is_(True),
                    User.participation_status == ParticipationStatus.APPROVED,
                )
            )
        ).all()
    )


async def service_recipients(session, record):
    from app.modules.maintenance.models import MaintenanceRevision
    from app.modules.vehicles.models import VerificationStatus
    from app.modules.workshops.models import WorkshopUser

    recipients = {record.author_user_id}
    revision = await session.get(MaintenanceRevision, record.current_revision_id)
    if revision is not None and revision.customer_user_id is not None:
        recipients.add(revision.customer_user_id)
    if record.workshop_id:
        recipients.update(
            (
                await session.scalars(
                    select(WorkshopUser.user_id).where(
                        WorkshopUser.workshop_id == record.workshop_id,
                        WorkshopUser.verification_status == VerificationStatus.VERIFIED,
                    )
                )
            ).all()
        )
    return recipients


async def notify_for_audit(session, audit):
    from app.modules.documents.models import Document
    from app.modules.maintenance.models import (
        MaintenanceRecord,
        MaintenanceRevision,
        ServiceDispute,
        ServiceInvitation,
    )
    from app.modules.payments.models import HistoryAccessGrant, SubscriptionPeriod
    from app.modules.vehicles.models import VehicleUser
    from app.modules.workshops.models import WorkshopClaim

    recipients = set()
    kind, target_type, target_id = None, audit.target_type, audit.target_id
    action = audit.action
    if action == "account_request.created":
        from app.modules.users.requests import AccountRequest

        request = await session.get(AccountRequest, target_id)
        recipients = await administrative_recipients(session)
        recipients.add(request.user_id)
        kind = "account_request"
    elif action == "auth.password_reset":
        recipients, kind = {target_id}, "password_changed"
    elif action == "participant.review":
        recipients, kind = {audit.target_id}, "participation_updated"
    elif action == "document.review":
        document = await session.get(Document, audit.target_id)
        recipients, kind = {document.owner_user_id}, "document_reviewed"
    elif action in {"vehicle_link.review", "vehicle_link.request_documents"}:
        link = await session.get(VehicleUser, audit.target_id)
        recipients = {link.user_id}
        kind = "documents_requested" if action.endswith("request_documents") else "vehicle_updated"
    elif action == "workshop_claim.review":
        claim = await session.get(WorkshopClaim, audit.target_id)
        recipients, kind = {claim.user_id}, "workshop_updated"
    elif action == "workshop_claim.request":
        recipients, kind = await administrative_recipients(session), "workshop_pending"
    elif action == "service_invitation.created":
        invitation = await session.get(ServiceInvitation, audit.target_id)
        user_id = await session.scalar(
            select(User.id).where(User.email == invitation.recipient_email)
        )
        await enqueue_notification(
            session,
            recipient_id=user_id,
            kind="service_invitation",
            target_type="service_invitation",
            target_id=invitation.id,
            dedupe_key=f"invitation:{invitation.id}",
        )
        return
    elif action == "service_invitation.accepted":
        invitation = await session.get(ServiceInvitation, audit.target_id)
        recipients, kind = {invitation.consumed_by_id}, "recognition_pending"
        target_type, target_id = "maintenance_record", invitation.record_id
    elif action in {"maintenance.review", "maintenance.acknowledge", "maintenance.revision"}:
        record = await session.get(MaintenanceRecord, audit.target_id)
        revision = await session.get(MaintenanceRevision, record.current_revision_id)
        if action == "maintenance.revision":
            if (
                revision is None
                or revision.revision_number == 1
                or revision.customer_user_id is None
            ):
                return
            recipients, kind = {revision.customer_user_id}, "recognition_pending"
        else:
            recipients, kind = await service_recipients(session, record), "service_updated"
    elif action.startswith("service_dispute."):
        dispute = await session.get(ServiceDispute, audit.target_id)
        record = await session.get(MaintenanceRecord, dispute.record_id)
        recipients = await service_recipients(session, record)
        recipients.update(await administrative_recipients(session))
        kind = "dispute_updated"
        target_type, target_id = "maintenance_record", record.id
    elif action in {"payments.benefit.granted", "payments.benefit.revoked"}:
        model = HistoryAccessGrant if target_type == "history_access_grant" else SubscriptionPeriod
        benefit = await session.get(model, audit.target_id)
        recipients, kind = {benefit.buyer_id}, "benefit_updated"
    elif action.startswith("payments.cancellation."):
        recipients, kind = {audit.target_id}, "benefit_updated"
    if kind is not None:
        for recipient in sorted(user_id for user_id in recipients if user_id is not None):
            await enqueue_notification(
                session,
                recipient_id=recipient,
                kind=kind,
                target_type=target_type,
                target_id=target_id,
                dedupe_key=f"audit:{audit.id}:recipient:{recipient}",
            )
