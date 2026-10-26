from fastapi import HTTPException
from sqlalchemy import exists, or_, select

from app.modules.audit.service import append_audit
from app.modules.maintenance.models import MaintenanceRecord, MaintenanceRevision
from app.modules.maintenance.revisions import current_revision, locked_record
from app.modules.vehicles.access import require_active_vehicle_link
from app.modules.vehicles.models import GarageValidationStatus, VehicleUser, VerificationStatus


async def acknowledge_service(session, record_id, revision_id, actor):
    record = await locked_record(session, record_id)
    revision = await current_revision(session, record)
    if revision.id != revision_id:
        raise HTTPException(status_code=409, detail="The service revision has changed")
    if revision.customer_user_id != actor.id:
        raise HTTPException(status_code=404, detail="Service not assigned to this customer")
    await require_active_vehicle_link(session, actor.id, record.vehicle_id)
    if record.dispute_open or revision.customer_acknowledgement == "disputed":
        raise HTTPException(
            status_code=409, detail="A disputed service requires a corrected revision"
        )
    if revision.customer_acknowledgement != "confirmed":
        revision.customer_acknowledgement = "confirmed"
        revision.review_version += 1
        await append_audit(
            session,
            actor_id=actor.id,
            action="maintenance.acknowledge",
            target_type="maintenance_record",
            target_id=record.id,
            version=revision.id,
        )
        await session.commit()
    return record


async def pending_customer_services(session, actor):
    return list(
        (
            await session.scalars(
                select(MaintenanceRecord)
                .join(
                    MaintenanceRevision,
                    MaintenanceRevision.id == MaintenanceRecord.current_revision_id,
                )
                .where(
                    MaintenanceRevision.customer_user_id == actor.id,
                    or_(
                        MaintenanceRecord.author_user_id == actor.id,
                        exists(
                            select(VehicleUser.id).where(
                                VehicleUser.user_id == actor.id,
                                VehicleUser.vehicle_id == MaintenanceRecord.vehicle_id,
                                VehicleUser.garage_status == GarageValidationStatus.ACTIVE,
                                VehicleUser.verification_status == VerificationStatus.VERIFIED,
                            )
                        ).correlate(MaintenanceRecord),
                    ),
                    MaintenanceRevision.customer_acknowledgement.in_(
                        ("awaiting_customer", "disputed")
                    ),
                )
                .order_by(MaintenanceRecord.id)
            )
        ).all()
    )
