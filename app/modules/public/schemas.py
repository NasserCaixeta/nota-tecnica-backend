from datetime import date
from enum import StrEnum

from pydantic import BaseModel


class CompletenessScore(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VehicleHistoryPreview(BaseModel):
    plate: str
    vehicle_found: bool
    maintenance_count: int
    first_maintenance_date: date | None
    last_maintenance_date: date | None
    categories: list[str]
    distinct_workshop_count: int
    completeness_score: CompletenessScore
