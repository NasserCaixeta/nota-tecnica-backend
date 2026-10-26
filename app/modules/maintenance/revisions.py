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


async def record_to_read(session, record, actor):
    revision = await current_revision(session, record)
    public_id = await session.scalar(
        published_maintenance_select()
        .with_only_columns(MaintenanceRecord.id)
        .where(MaintenanceRecord.id == record.id)
    )
    from app.modules.vehicles.access import require_active_vehicle_link
    from app.modules.workshops.claims import require_workshop_responsibility

    involved = actor.is_admin or record.author_user_id == actor.id
    if not involved and record.origin == "workshop":
        try:
            await require_workshop_responsibility(session, actor.id, record.workshop_id)
            involved = True
        except HTTPException:
            pass
    if not involved and revision.customer_user_id == actor.id:
        await require_active_vehicle_link(session, actor.id, record.vehicle_id)
        involved = True
    if not involved:
        await require_active_vehicle_link(session, actor.id, record.vehicle_id)
        if public_id is None:
            raise HTTPException(status_code=404, detail="Maintenance record not found")
        from app.modules.maintenance.projections import build_published_maintenance_read
        from app.modules.workshops.models import Workshop

        workshop = await session.get(Workshop, record.workshop_id) if record.workshop_id else None
        return build_published_maintenance_read(record, revision, workshop)
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
    permissions = dict.fromkeys(
        ("can_edit", "can_submit", "can_acknowledge", "can_dispute", "can_invite", "can_review"),
        False,
    )
    if actor is not None and record.superseded_by_id is None:
        from app.modules.garage.policy import require_garage_write
        from app.modules.maintenance.service import can_operate_record
        from app.modules.vehicles.access import require_active_vehicle_link

        try:
            await can_operate_record(session, record, actor)
            if record.origin == "customer":
                await require_garage_write(session, actor.id, record.vehicle_id)
            permissions["can_edit"] = True
            permissions["can_invite"] = record.origin == "workshop"
            if record.origin == "customer":
                await require_active_vehicle_link(session, actor.id, record.vehicle_id)
            from app.modules.maintenance.moderation import revision_evidence
            from app.modules.maintenance.publication import SERVICE_EVIDENCE_TYPES

            documents = await revision_evidence(session, revision.id)
            permissions["can_submit"] = revision.editorial_status == "draft" and any(
                d.storage_verified and d.document_type in SERVICE_EVIDENCE_TYPES for d in documents
            )
        except HTTPException:
            pass
        if revision.customer_user_id == actor.id:
            try:
                await require_active_vehicle_link(session, actor.id, record.vehicle_id)
                from app.modules.workshops.models import WorkshopUser

                responsible = await session.scalar(
                    select(WorkshopUser.id).where(
                        WorkshopUser.user_id == actor.id,
                        WorkshopUser.workshop_id == record.workshop_id,
                    )
                )
                permissions["can_review"] = public_id is not None and responsible is None
                permissions["can_dispute"] = not record.dispute_open
                permissions["can_acknowledge"] = (
                    not record.dispute_open
                    and revision.customer_acknowledgement == "awaiting_customer"
                )
            except HTTPException:
                pass
    return MaintenanceRecordRead(**values, published=public_id is not None, permissions=permissions)
