from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.maintenance.models import MaintenanceCategory, MaintenanceRecord, MaintenanceStatus
from app.modules.ranking.schemas import WorkshopRankingItem, WorkshopRankingResponse
from app.modules.workshops.models import Workshop

SCORE_VERSION = "initial_v1"
SCORE_EXPLANATION = (
    "Initial score based on completed service volume and on-time delivery. "
    "Cost metrics are displayed but not yet used as a penalty."
)


def delivery_days(entry_date: date | None, actual_delivery_date: date | None) -> int | None:
    if entry_date is None or actual_delivery_date is None:
        return None
    return (actual_delivery_date - entry_date).days


def calculate_score(completed_services_count: int, on_time_rate: float | None) -> float:
    volume_component = min(completed_services_count, 20) / 20 * 30
    deadline_component = (on_time_rate * 40) if on_time_rate is not None else 20
    cost_component = 30
    return round(volume_component + deadline_component + cost_component, 2)


async def list_workshop_ranking(
    session: AsyncSession,
    city: str | None,
    state: str | None,
    category: MaintenanceCategory | None,
    limit: int,
) -> WorkshopRankingResponse:
    statement = (
        select(Workshop, MaintenanceRecord)
        .join(MaintenanceRecord, MaintenanceRecord.workshop_id == Workshop.id)
        .where(MaintenanceRecord.status == MaintenanceStatus.COMPLETED)
    )
    if city is not None:
        statement = statement.where(Workshop.city == city)
    if state is not None:
        statement = statement.where(Workshop.state == state.upper())
    if category is not None:
        statement = statement.where(MaintenanceRecord.category == category)
    rows = (await session.execute(statement)).all()

    grouped: dict[int, tuple[Workshop, list[MaintenanceRecord]]] = {}
    for workshop, record in rows:
        grouped.setdefault(workshop.id, (workshop, []))[1].append(record)

    items: list[WorkshopRankingItem] = []
    for workshop, records in grouped.values():
        count = len(records)
        total_cost = sum((record.total_cost for record in records), Decimal("0.00"))
        labor_cost = sum((record.labor_cost for record in records), Decimal("0.00"))
        parts_cost = sum((record.parts_cost for record in records), Decimal("0.00"))
        deadline_records = [
            record
            for record in records
            if record.promised_delivery_date is not None and record.actual_delivery_date is not None
        ]
        on_time_rate = None
        if deadline_records:
            on_time_count = sum(
                1
                for record in deadline_records
                if record.actual_delivery_date <= record.promised_delivery_date
            )
            on_time_rate = on_time_count / len(deadline_records)
        durations = [
            value
            for value in (
                delivery_days(record.entry_date, record.actual_delivery_date)
                for record in records
            )
            if value is not None
        ]
        average_delivery_days = sum(durations) / len(durations) if durations else None
        items.append(
            WorkshopRankingItem(
                workshop_id=workshop.id,
                trade_name=workshop.trade_name,
                city=workshop.city,
                state=workshop.state,
                specialties=workshop.specialties,
                completed_services_count=count,
                average_total_cost=total_cost / count,
                average_labor_cost=labor_cost / count,
                average_parts_cost=parts_cost / count,
                on_time_rate=on_time_rate,
                average_delivery_days=average_delivery_days,
                score=calculate_score(count, on_time_rate),
                score_version=SCORE_VERSION,
            )
        )
    items.sort(key=lambda item: item.score, reverse=True)
    return WorkshopRankingResponse(
        score_version=SCORE_VERSION,
        score_explanation=SCORE_EXPLANATION,
        items=items[:limit],
    )
