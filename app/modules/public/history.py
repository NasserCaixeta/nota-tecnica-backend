from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import get_approved_participant
from app.modules.maintenance.models import MaintenanceRecord, MaintenanceRevision
from app.modules.maintenance.projections import (
    PublishedMaintenanceRead,
    build_published_maintenance_read,
)
from app.modules.maintenance.publication import published_maintenance_select
from app.modules.payments.access import active_relationship, current_history_grant
from app.modules.public.service import normalize_plate
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from app.modules.workshops.models import Workshop

router = APIRouter(prefix="/history", tags=["history"])


class HistoryAccessRead(BaseModel):
    source: Literal["relationship", "purchase"]
    expires_at: datetime | None = None


class VehicleHistoryRead(BaseModel):
    plate: str
    access: HistoryAccessRead
    records: list[PublishedMaintenanceRead]


@router.get("/vehicles/{plate}", response_model=VehicleHistoryRead)
async def read_vehicle_history(
    plate: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_approved_participant)],
):
    plate = normalize_plate(plate)
    vehicle = await session.scalar(select(Vehicle).where(Vehicle.plate == plate))
    access = None
    if vehicle is not None:
        if await active_relationship(session, user.id, vehicle.id):
            access = HistoryAccessRead(source="relationship")
        else:
            grant = await current_history_grant(session, user.id, vehicle.id, datetime.now(UTC))
            if grant is not None:
                access = HistoryAccessRead(source="purchase", expires_at=grant.expires_at)
    if access is None:
        # Same response for an unknown plate and a private vehicle without rights.
        raise HTTPException(403, "A validated relationship or active history purchase is required")
    rows = (
        await session.execute(
            published_maintenance_select()
            .add_columns(MaintenanceRevision, Workshop)
            .outerjoin(Workshop, Workshop.id == MaintenanceRecord.workshop_id)
            .where(MaintenanceRecord.vehicle_id == vehicle.id)
            .order_by(MaintenanceRecord.service_date.desc(), MaintenanceRecord.id.desc())
        )
    ).all()
    return VehicleHistoryRead(
        plate=plate,
        access=access,
        records=[
            build_published_maintenance_read(record, revision, workshop)
            for record, revision, workshop in rows
        ],
    )
