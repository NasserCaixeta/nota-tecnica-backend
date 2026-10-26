from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.modules.garage.policy import require_garage_write
from app.modules.maintenance.models import MaintenanceRecord
from app.modules.maintenance.publication import published_maintenance_select
from app.modules.maintenance.revisions import create_revision, current_revision, locked_record
from app.modules.maintenance.schemas import MaintenanceRecordCreate
from app.modules.vehicles.access import require_active_vehicle_link, require_vehicle_link
from app.modules.vehicles.models import Vehicle, VehicleUser
from app.modules.workshops.claims import require_workshop_responsibility
from app.modules.workshops.models import Workshop


async def ensure_user_vehicle_link(session, vehicle_id, user):
    await require_vehicle_link(session, user.id, vehicle_id)
    return await session.get(Vehicle, vehicle_id)


async def ensure_workshop_exists(session, workshop_id):
    if workshop_id is not None and await session.get(Workshop, workshop_id) is None:
        raise HTTPException(status_code=404, detail="Workshop not found")


def calculate_total(labor_cost, parts_cost):
    return labor_cost + parts_cost


async def create_maintenance_record(session, vehicle_id, payload, user):
    await ensure_user_vehicle_link(session, vehicle_id, user)
    await require_garage_write(session, user.id, vehicle_id)
    await ensure_workshop_exists(session, payload.workshop_id)
    record = MaintenanceRecord(
        **payload.model_dump(),
        vehicle_id=vehicle_id,
        author_user_id=user.id,
        origin="customer",
        total_cost=calculate_total(payload.labor_cost, payload.parts_cost),
    )
    session.add(record)
    await session.flush()
    await create_revision(session, record, actor_id=user.id)
    await session.commit()
    return record


async def create_workshop_maintenance(session, workshop_id, payload, user):
    await require_workshop_responsibility(session, user.id, workshop_id)
    if payload.workshop_id not in (None, workshop_id):
        raise HTTPException(status_code=422, detail="Workshop does not match the route")
    vehicle = await session.scalar(select(Vehicle).where(Vehicle.plate == payload.plate))
    if vehicle is None:
        vehicle = Vehicle(plate=payload.plate)
        try:
            async with session.begin_nested():
                session.add(vehicle)
                await session.flush()
        except IntegrityError:
            vehicle = await session.scalar(select(Vehicle).where(Vehicle.plate == payload.plate))
            if vehicle is None:
                raise
    record = MaintenanceRecord(
        **payload.model_dump(exclude={"plate", "workshop_id"}),
        workshop_id=workshop_id,
        vehicle_id=vehicle.id,
        author_user_id=user.id,
        origin="workshop",
        total_cost=calculate_total(payload.labor_cost, payload.parts_cost),
    )
    session.add(record)
    await session.flush()
    await create_revision(session, record, actor_id=user.id)
    await session.commit()
    return record


async def can_operate_record(session, record, user):
    if record.origin == "workshop":
        await require_workshop_responsibility(session, user.id, record.workshop_id)
    elif record.author_user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the service author can change it")


async def list_workshop_maintenance(session, workshop_id, user):
    await require_workshop_responsibility(session, user.id, workshop_id)
    return list(
        (
            await session.scalars(
                select(MaintenanceRecord)
                .where(
                    MaintenanceRecord.workshop_id == workshop_id,
                    MaintenanceRecord.origin == "workshop",
                )
                .order_by(MaintenanceRecord.id.desc())
            )
        ).all()
    )


async def list_vehicle_maintenance_records(session, vehicle_id, user):
    link = await require_vehicle_link(session, user.id, vehicle_id)
    from app.modules.vehicles.models import GarageValidationStatus, VerificationStatus

    visible = MaintenanceRecord.author_user_id == user.id
    if (
        link.verification_status == VerificationStatus.VERIFIED
        and link.garage_status == GarageValidationStatus.ACTIVE
    ):
        published_ids = published_maintenance_select().with_only_columns(MaintenanceRecord.id)
        from app.modules.maintenance.models import MaintenanceRevision

        assigned = (
            select(MaintenanceRevision.record_id)
            .where(
                MaintenanceRevision.customer_user_id == user.id,
                MaintenanceRevision.id == MaintenanceRecord.current_revision_id,
            )
            .correlate(MaintenanceRecord)
            .exists()
        )
        visible = or_(visible, MaintenanceRecord.id.in_(published_ids), assigned)
    return list(
        (
            await session.scalars(
                select(MaintenanceRecord)
                .where(MaintenanceRecord.vehicle_id == vehicle_id, visible)
                .order_by(MaintenanceRecord.service_date.desc(), MaintenanceRecord.id.desc())
            )
        ).all()
    )


async def get_maintenance_record(session, record_id, user):
    record = await session.get(MaintenanceRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    if user.is_admin or record.author_user_id == user.id:
        return record
    if record.origin == "workshop":
        try:
            await require_workshop_responsibility(session, user.id, record.workshop_id)
            return record
        except HTTPException:
            pass
    link = await session.scalar(
        select(VehicleUser).where(
            VehicleUser.user_id == user.id, VehicleUser.vehicle_id == record.vehicle_id
        )
    )
    if link:
        await require_active_vehicle_link(session, user.id, record.vehicle_id)
        revision = await current_revision(session, record)
        if revision.customer_user_id == user.id:
            return record
        if await session.scalar(
            published_maintenance_select().where(MaintenanceRecord.id == record.id)
        ):
            return record
    raise HTTPException(status_code=404, detail="Maintenance record not found")


async def update_maintenance_record(session, record_id, payload, user):
    record = await locked_record(session, record_id)
    await can_operate_record(session, record, user)
    if record.origin == "customer":
        await require_garage_write(session, user.id, record.vehicle_id)
    if payload.expected_revision_id and payload.expected_revision_id != record.current_revision_id:
        raise HTTPException(status_code=409, detail="The service revision has changed")
    updates = payload.model_dump(exclude_unset=True, exclude={"expected_revision_id"})
    if record.origin == "workshop" and "workshop_id" in updates:
        if updates["workshop_id"] != record.workshop_id:
            raise HTTPException(status_code=422, detail="Workshop origin cannot be reassigned")
    values = {key: getattr(record, key) for key in MaintenanceRecordCreate.model_fields}
    values.update(updates)
    try:
        validated = MaintenanceRecordCreate(**values)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid service data or dates") from exc
    if any(getattr(record, key) != value for key, value in validated.model_dump().items()):
        await ensure_workshop_exists(session, validated.workshop_id)
        for key, value in validated.model_dump().items():
            setattr(record, key, value)
        record.total_cost = calculate_total(record.labor_cost, record.parts_cost)
        await create_revision(session, record, actor_id=user.id)
    await session.commit()
    return record
