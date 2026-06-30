from decimal import Decimal

from pydantic import BaseModel


class WorkshopRankingItem(BaseModel):
    workshop_id: int
    trade_name: str
    city: str
    state: str
    specialties: list[str]
    completed_services_count: int
    average_total_cost: Decimal
    average_labor_cost: Decimal
    average_parts_cost: Decimal
    on_time_rate: float | None
    average_delivery_days: float | None
    score: float
    score_version: str


class WorkshopRankingResponse(BaseModel):
    score_version: str
    score_explanation: str
    items: list[WorkshopRankingItem]
