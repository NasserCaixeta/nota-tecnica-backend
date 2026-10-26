from fastapi import HTTPException
from sqlalchemy import select

from app.modules.audit.service import append_audit
from app.modules.maintenance.models import MaintenanceRecord, MaintenanceRevision
from app.modules.maintenance.publication import published_maintenance_select
from app.modules.maintenance.schemas import MaintenanceRecordCreate, MaintenanceRecordRead


async def locked_record(session, record_id):
    record = await session.scalar(
        select(MaintenanceRecord)
        .where(MaintenanceRecord.id == record_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    return record


async def current_revision(session, record):
    revision = await session.get(MaintenanceRevision, record.current_revision_id)
    if revision is None or revision.record_id != record.id:
        raise HTTPException(status_code=409, detail="The maintenance revision is unavailable")
    return revision


async def create_revision(session, record, *, actor_id):
    previous = await current_revision(session, record) if record.current_revision_id else None
    fields = MaintenanceRecordCreate.model_fields
    snapshot = MaintenanceRecordCreate(**{key: getattr(record, key) for key in fields})
    revision = MaintenanceRevision(
        record_id=record.id,
        revision_number=previous.revision_number + 1 if previous else 1,
        snapshot=snapshot.model_dump(mode="json"),
        editorial_status="cancelled" if record.status == "cancelled" else "draft",
        customer_acknowledgement="author_acknowledged"
        if record.origin == "customer"
        else "awaiting_customer",
        customer_user_id=record.author_user_id
        if record.origin == "customer"
        else previous.customer_user_id
        if previous
        else None,
    )
    session.add(revision)
    await session.flush()
    record.current_revision_id = revision.id
    await append_audit(
        session,
        actor_id=actor_id,
        action="maintenance.revision",
        target_type="maintenance_record",
        target_id=record.id,
        version=revision.revision_number,
    )
    return revision


async def record_to_read(session, record):
    revision = await current_revision(session, record)
    public_id = await session.scalar(
        published_maintenance_select()
        .with_only_columns(MaintenanceRecord.id)
        .where(MaintenanceRecord.id == record.id)
    )
    values = {
        key: getattr(record, key)
        for key in MaintenanceRecordRead.model_fields
        if hasattr(record, key)
    }
    for key in (
        "editorial_status",
        "admin_status",
        "customer_acknowledgement",
        "customer_user_id",
        "review_version",
        "public_description",
        "review_reason",
    ):
        values[key] = getattr(revision, key)
    return MaintenanceRecordRead(**values, published=public_id is not None)
