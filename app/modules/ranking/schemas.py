from decimal import Decimal

from pydantic import BaseModel, Field


class WorkshopRankingItem(BaseModel):
    workshop_id: int
    trade_name: str
    city: str
    state: str
    specialties: list[str]
    completed_services_count: int
    average_total_cost: Decimal | None
    average_labor_cost: Decimal | None
    average_parts_cost: Decimal | None
    on_time_rate: float | None
    average_delivery_days: float | None
    average_stars: Decimal | None
    review_count: int
    measured_deadline_count: int
    on_time_count: int
    score: Decimal | None
    eligible_for_ranking: bool
    sample_label: str
    score_version: str


class WorkshopRankingResponse(BaseModel):
    score_version: str
    score_explanation: str
    items: list[WorkshopRankingItem]
    unranked_items: list[WorkshopRankingItem] = Field(default_factory=list)
