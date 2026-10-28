from fastapi import HTTPException
from sqlalchemy import select

from app.modules.audit.service import append_audit
from app.modules.documents.models import Document, DocumentReviewStatus
from app.modules.garage.policy import require_garage_write
from app.modules.maintenance.models import MaintenanceRecord, MaintenanceRevision
from app.modules.maintenance.publication import SERVICE_EVIDENCE_TYPES
from app.modules.maintenance.revisions import current_revision, locked_record
from app.modules.maintenance.service import can_operate_record
from app.modules.vehicles.access import require_active_vehicle_link


async def revision_evidence(session, revision_id):
    return list(
        (
            await session.scalars(
                select(Document)
                .where(Document.maintenance_revision_id == revision_id)
                .order_by(Document.id)
            )
        ).all()
    )


async def submit_maintenance(session, record_id, payload, user):
    record = await locked_record(session, record_id)
    await can_operate_record(session, record, user)
    if record.current_revision_id != payload.revision_id:
        raise HTTPException(status_code=409, detail="The service revision has changed")
    if record.origin == "customer":
        await require_active_vehicle_link(session, user.id, record.vehicle_id)
        await require_garage_write(session, user.id, record.vehicle_id)
    revision = await current_revision(session, record)
    if revision.editorial_status == "cancelled":
        raise HTTPException(status_code=409, detail="Cancelled services cannot be submitted")
    if revision.editorial_status == "submitted":
        raise HTTPException(status_code=409, detail="This revision is already submitted")
    if not any(
        d.storage_verified and d.document_type in SERVICE_EVIDENCE_TYPES
        for d in await revision_evidence(session, revision.id)
    ):
        raise HTTPException(status_code=409, detail="A verified service receipt is required")
    revision.editorial_status = "submitted"
    revision.admin_status = "pending"
    revision.review_version += 1
    await append_audit(
        session,
        actor_id=user.id,
        action="maintenance.submit",
        target_type="maintenance_record",
        target_id=record.id,
        version=revision.review_version,
        metadata={"revision_id": revision.id},
    )
    await session.commit()
    return record


async def review_maintenance(session, record_id, payload, actor):
    record = await locked_record(session, record_id)
    revision = await current_revision(session, record)
    if actor.id in (record.author_user_id, revision.customer_user_id):
        raise HTTPException(
            status_code=409, detail="Administrators cannot review their own service"
        )
    if payload.revision_id != revision.id or payload.expected_version != revision.review_version:
        raise HTTPException(status_code=409, detail="The service review has changed")
    if revision.editorial_status != "submitted":
        raise HTTPException(status_code=409, detail="The service must be submitted")
    if payload.decision == "approved":
        if not payload.public_description:
            raise HTTPException(status_code=422, detail="A reviewed public description is required")
        if not any(
            d.storage_verified
            and d.review_status == DocumentReviewStatus.APPROVED
            and d.document_type in SERVICE_EVIDENCE_TYPES
            for d in await revision_evidence(session, revision.id)
        ):
            raise HTTPException(status_code=409, detail="An approved service receipt is required")
    revision.admin_status = payload.decision
    revision.review_reason = payload.reason
    revision.public_description = (
        payload.public_description if payload.decision == "approved" else None
    )
    revision.review_version += 1
    if payload.decision == "changes_requested":
        revision.editorial_status = "draft"
    await append_audit(
        session,
        actor_id=actor.id,
        action="maintenance.review",
        target_type="maintenance_record",
        target_id=record.id,
        version=revision.review_version,
        reason=payload.reason,
        metadata={"revision_id": revision.id, "decision": payload.decision},
    )
    await session.commit()
    return record


async def pending_maintenance(session):
    return list(
        (
            await session.scalars(
                select(MaintenanceRecord)
                .join(
                    MaintenanceRevision,
                    MaintenanceRevision.id == MaintenanceRecord.current_revision_id,
                )
                .where(
                    MaintenanceRevision.editorial_status == "submitted",
                    MaintenanceRevision.admin_status == "pending",
                )
                .order_by(MaintenanceRecord.id)
            )
        ).all()
    )
