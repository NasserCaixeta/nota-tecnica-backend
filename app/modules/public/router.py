from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.public.schemas import VehicleHistoryPreview
from app.modules.public.service import get_vehicle_history_preview

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/vehicles/{plate}/history-preview", response_model=VehicleHistoryPreview)
async def read_vehicle_history_preview(
    plate: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VehicleHistoryPreview:
    return await get_vehicle_history_preview(session, plate)
