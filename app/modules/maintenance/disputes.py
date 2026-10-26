from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.integrations.storage.r2 import build_document_storage_key
from app.modules.audit.service import append_audit
from app.modules.documents.models import (
    Document,
    DocumentProcessingStatus,
    DocumentReviewStatus,
    DocumentUploadStatus,
)
from app.modules.documents.schemas import DocumentRead, DocumentUploadIntentRead
from app.modules.maintenance.models import ServiceDispute, ServiceDisputeMessage
from app.modules.maintenance.revisions import current_revision, locked_record
from app.modules.vehicles.access import require_active_vehicle_link
from app.modules.vehicles.models import Vehicle
from app.modules.workshops.claims import require_workshop_responsibility


async def open_dispute(session, record_id, payload, actor):
    record = await locked_record(session, record_id)
    revision = await current_revision(session, record)
    if revision.id != payload.revision_id:
        raise HTTPException(status_code=409, detail="The service revision has changed")
    if revision.customer_user_id != actor.id:
        raise HTTPException(status_code=404, detail="Service not assigned to this customer")
    await require_active_vehicle_link(session, actor.id, record.vehicle_id)
    previous = list(
        (
            await session.scalars(
                select(ServiceDispute).where(ServiceDispute.record_id == record.id)
            )
        ).all()
    )
    if record.dispute_open or any(
        d.reason.casefold() == payload.reason.casefold() for d in previous
    ):
        raise HTTPException(
            status_code=409, detail="An open dispute or repeated reason already exists"
        )
    dispute = ServiceDispute(
        record_id=record.id,
        revision_id=revision.id,
        customer_user_id=actor.id,
        reason=payload.reason,
    )
    session.add(dispute)
    await session.flush()
    record.dispute_open = True
    revision.customer_acknowledgement = "disputed"
    revision.review_version += 1
    await append_audit(
        session,
        actor_id=actor.id,
        action="service_dispute.opened",
        target_type="service_dispute",
        target_id=dispute.id,
        version=1,
        reason=payload.reason,
    )
    await session.commit()
    return dispute


async def require_dispute_reader(session, dispute_id, actor):
    dispute = await session.get(ServiceDispute, dispute_id)
    if dispute is None:
        raise HTTPException(status_code=404, detail="Dispute not found")
    if actor.is_admin or dispute.customer_user_id == actor.id:
        return dispute
    from app.modules.maintenance.models import MaintenanceRecord

    record = await session.get(MaintenanceRecord, dispute.record_id)
    if record.origin == "workshop":
        await require_workshop_responsibility(session, actor.id, record.workshop_id)
        return dispute
    raise HTTPException(status_code=404, detail="Dispute not found")


async def dispute_to_read(session, dispute, actor):
    messages = list(
        (
            await session.scalars(
                select(ServiceDisputeMessage)
                .where(ServiceDisputeMessage.dispute_id == dispute.id)
                .order_by(ServiceDisputeMessage.id)
            )
        ).all()
    )
    documents = list(
        (
            await session.scalars(select(Document).where(Document.service_dispute_id == dispute.id))
        ).all()
    )
    return {
        **{c.name: getattr(dispute, c.name) for c in ServiceDispute.__table__.columns},
        "messages": [
            {"id": m.id, "actor_id": m.actor_id, "body": m.body, "created_at": m.created_at}
            for m in messages
        ],
        "documents": [
            DocumentRead.model_validate(d)
            for d in documents
            if actor.is_admin or d.owner_user_id == actor.id
        ],
    }


async def review_dispute(session, dispute_id, payload, actor):
    original = await session.get(ServiceDispute, dispute_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Dispute not found")
    record = await locked_record(session, original.record_id)
    dispute = await session.scalar(
        select(ServiceDispute)
        .where(ServiceDispute.id == dispute_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if dispute.customer_user_id == actor.id or record.author_user_id == actor.id:
        raise HTTPException(
            status_code=409, detail="Administrators cannot review their own dispute"
        )
    if dispute.review_version != payload.expected_version or dispute.status != "open":
        raise HTTPException(status_code=409, detail="The dispute review has changed")
    dispute.resolution = payload.resolution
    dispute.resolution_reason = payload.reason
    dispute.review_version += 1
    if payload.resolution == "request_changes":
        revision = await current_revision(session, record)
        revision.admin_status = "changes_requested"
        revision.editorial_status = "draft"
        revision.review_version += 1
    else:
        dispute.status = "closed"
        dispute.resolved_at = datetime.now(UTC)
        record.dispute_open = False
    # The customer's acknowledgement is never changed by an administrative decision.
    await append_audit(
        session,
        actor_id=actor.id,
        action="service_dispute.reviewed",
        target_type="service_dispute",
        target_id=dispute.id,
        version=dispute.review_version,
        reason=payload.reason,
        metadata={"resolution": payload.resolution},
    )
    await session.commit()
    return dispute


async def reply_dispute(session, dispute_id, payload, actor):
    dispute = await require_dispute_reader(session, dispute_id, actor)
    if dispute.status != "open":
        raise HTTPException(status_code=409, detail="The dispute is closed")
    message = ServiceDisputeMessage(dispute_id=dispute.id, actor_id=actor.id, body=payload.body)
    session.add(message)
    await append_audit(
        session,
        actor_id=actor.id,
        action="service_dispute.reply",
        target_type="service_dispute",
        target_id=dispute.id,
    )
    await session.commit()
    return dispute


async def upload_dispute_evidence(session, dispute_id, payload, actor, storage):
    dispute = await require_dispute_reader(session, dispute_id, actor)
    if dispute.status != "open" or payload.maintenance_record_id is not None:
        raise HTTPException(status_code=409, detail="Evidence requires an open dispute")
    from app.modules.maintenance.models import MaintenanceRecord

    record = await session.get(MaintenanceRecord, dispute.record_id)
    vehicle = await session.get(Vehicle, record.vehicle_id)
    key = build_document_storage_key(vehicle.plate, payload.file_name)
    document = Document(
        owner_user_id=actor.id,
        vehicle_id=vehicle.id,
        service_dispute_id=dispute.id,
        document_type=payload.document_type,
        file_name=payload.file_name,
        original_file_name=payload.file_name,
        content_type=payload.content_type,
        file_size_bytes=payload.file_size_bytes,
        storage_key=key,
        review_status=DocumentReviewStatus.PENDING,
        upload_status=DocumentUploadStatus.PENDING,
        processing_status=DocumentProcessingStatus.NOT_REQUESTED,
    )
    session.add(document)
    await session.commit()
    signed = storage.create_presigned_upload_url(
        key, payload.content_type, get_settings().document_upload_url_expires_seconds
    )
    return DocumentUploadIntentRead(
        document=document,
        storage_key=key,
        upload_url=signed.upload_url,
        required_headers=signed.required_headers,
    )
