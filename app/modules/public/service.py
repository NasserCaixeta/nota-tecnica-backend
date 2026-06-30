from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.maintenance.models import MaintenanceRecord, MaintenanceStatus
from app.modules.public.schemas import CompletenessScore, VehicleHistoryPreview
from app.modules.vehicles.models import Vehicle


def normalize_plate(value: str) -> str:
    return "".join(character for character in value if character.isalnum()).upper()


def score_for_count(count: int) -> CompletenessScore:
    if count == 0:
        return CompletenessScore.NONE
    if count < 3:
        return CompletenessScore.LOW
    if count < 8:
        return CompletenessScore.MEDIUM
    return CompletenessScore.HIGH


async def get_vehicle_history_preview(session: AsyncSession, plate: str) -> VehicleHistoryPreview:
    normalized_plate = normalize_plate(plate)
    vehicle = (
        await session.execute(select(Vehicle).where(Vehicle.plate == normalized_plate))
    ).scalar_one_or_none()
    if vehicle is None:
        return VehicleHistoryPreview(
            plate=normalized_plate,
            vehicle_found=False,
            maintenance_count=0,
            first_maintenance_date=None,
            last_maintenance_date=None,
            categories=[],
            distinct_workshop_count=0,
            completeness_score=CompletenessScore.NONE,
        )

    rows = await session.execute(
        select(MaintenanceRecord).where(
            MaintenanceRecord.vehicle_id == vehicle.id,
            MaintenanceRecord.status == MaintenanceStatus.COMPLETED,
        )
    )
    records = list(rows.scalars().all())
    dates = [record.service_date for record in records]
    categories = sorted({record.category.value for record in records})
    workshop_ids = {record.workshop_id for record in records if record.workshop_id is not None}
    return VehicleHistoryPreview(
        plate=normalized_plate,
        vehicle_found=True,
        maintenance_count=len(records),
        first_maintenance_date=min(dates) if dates else None,
        last_maintenance_date=max(dates) if dates else None,
        categories=categories,
        distinct_workshop_count=len(workshop_ids),
        completeness_score=score_for_count(len(records)),
    )
