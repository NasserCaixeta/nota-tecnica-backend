from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PilotScoreInput:
    service_count: int
    average_stars: Decimal | None
    measured_deadlines: int
    on_time_count: int


@dataclass(frozen=True)
class PilotScore:
    score: Decimal | None
    eligible_for_ranking: bool
    sample_label: str


def calculate_pilot_score(data: PilotScoreInput) -> PilotScore:
    if data.service_count == 0:
        return PilotScore(None, False, "no_data")
    volume = Decimal(10) * min(Decimal(data.service_count) / 20, Decimal(1))
    weighted = Decimal(".2") * volume
    weights = Decimal(".2")
    if data.average_stars is not None:
        weighted += Decimal(".4") * data.average_stars * 2
        weights += Decimal(".4")
    if data.measured_deadlines:
        weighted += Decimal(".4") * Decimal(data.on_time_count) / data.measured_deadlines * 10
        weights += Decimal(".4")
    if weights == Decimal(".2"):
        return PilotScore(None, False, "insufficient_quality_data")
    return PilotScore(
        weighted / weights,
        data.service_count >= 5,
        "sufficient" if data.service_count >= 5 else "small_sample",
    )
