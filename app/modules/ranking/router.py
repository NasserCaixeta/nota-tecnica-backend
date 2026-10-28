from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import enforce_query_budget
from app.db.session import get_db
from app.modules.maintenance.models import MaintenanceCategory
from app.modules.ranking.schemas import WorkshopRankingResponse
from app.modules.ranking.service import get_workshop_performance, list_workshop_ranking

router = APIRouter(
    prefix="/public/workshops", tags=["ranking"], dependencies=[Depends(enforce_query_budget)]
)


@router.get("/ranking", response_model=WorkshopRankingResponse)
async def read_workshop_ranking(
    session: Annotated[AsyncSession, Depends(get_db)],
    city: str | None = None,
    state: str | None = None,
    category: MaintenanceCategory | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> WorkshopRankingResponse:
    return await list_workshop_ranking(session, city, state, category, limit)


@router.get("/{workshop_id}/performance")
async def read_workshop_performance(
    workshop_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await get_workshop_performance(session, workshop_id)
