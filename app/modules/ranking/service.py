from datetime import date
from decimal import Decimal

from sqlalchemy import exists, select

from app.modules.maintenance.models import MaintenanceRecord, MaintenanceRevision
from app.modules.maintenance.publication import published_maintenance_select
from app.modules.ranking.models import ServiceReview
from app.modules.ranking.schemas import WorkshopRankingItem, WorkshopRankingResponse
from app.modules.ranking.scoring import PilotScoreInput, calculate_pilot_score
from app.modules.vehicles.models import VerificationStatus
from app.modules.workshops.models import Workshop, WorkshopUser

SCORE_VERSION = "pilot_v1"
SCORE_EXPLANATION = (
    "Escala de 0 a 10: avaliação 40%, prazo 40% e volume 20% (satura em 20 serviços). "
    "Componentes ausentes são excluídos e os pesos normalizados. "
    "Posição exige ao menos 5 serviços e avaliação ou prazo mensurável. Preço não altera a nota."
)


def delivery_days(entry_date: date | None, actual_delivery_date: date | None) -> int | None:
    if entry_date is None or actual_delivery_date is None:
        return None
    return (actual_delivery_date - entry_date).days


async def workshop_metrics(session, workshop, records):
    record_ids = [r.id for r in records]
    reviews = (
        list(
            (
                await session.scalars(
                    select(ServiceReview)
                    .join(MaintenanceRecord, ServiceReview.record_id == MaintenanceRecord.id)
                    .join(
                        MaintenanceRevision,
                        MaintenanceRevision.id == MaintenanceRecord.current_revision_id,
                    )
                    .where(
                        ServiceReview.record_id.in_(record_ids),
                        ServiceReview.revision_id == MaintenanceRecord.current_revision_id,
                        ServiceReview.customer_user_id == MaintenanceRevision.customer_user_id,
                        ~exists(
                            select(WorkshopUser.id).where(
                                WorkshopUser.workshop_id == workshop.id,
                                WorkshopUser.user_id == ServiceReview.customer_user_id,
                            )
                        ).correlate(ServiceReview),
                    )
                )
            ).all()
        )
        if record_ids
        else []
    )
    count = len(records)
    deadlines = [r for r in records if r.promised_delivery_date and r.actual_delivery_date]
    on_time_count = sum(r.actual_delivery_date <= r.promised_delivery_date for r in deadlines)
    average_stars = (
        sum((Decimal(r.stars) for r in reviews), Decimal(0)) / len(reviews) if reviews else None
    )
    score = calculate_pilot_score(
        PilotScoreInput(count, average_stars, len(deadlines), on_time_count)
    )
    durations = [
        days
        for r in records
        if (days := delivery_days(r.entry_date, r.actual_delivery_date)) is not None
    ]

    def average(field):
        return sum((getattr(r, field) for r in records), Decimal(0)) / count if count else None

    item = WorkshopRankingItem(
        workshop_id=workshop.id,
        trade_name=workshop.trade_name,
        city=workshop.city,
        state=workshop.state,
        specialties=workshop.specialties,
        completed_services_count=count,
        average_total_cost=average("total_cost"),
        average_labor_cost=average("labor_cost"),
        average_parts_cost=average("parts_cost"),
        average_stars=average_stars,
        review_count=len(reviews),
        measured_deadline_count=len(deadlines),
        on_time_count=on_time_count,
        on_time_rate=on_time_count / len(deadlines) if deadlines else None,
        average_delivery_days=sum(durations) / len(durations) if durations else None,
        score=score.score.quantize(Decimal(".1")) if score.score is not None else None,
        eligible_for_ranking=score.eligible_for_ranking,
        sample_label=score.sample_label,
        score_version=SCORE_VERSION,
    )
    return item, score.score, reviews


async def list_workshop_ranking(session, city, state, category, limit):
    statement = (
        select(Workshop, MaintenanceRecord)
        .join(MaintenanceRecord, MaintenanceRecord.workshop_id == Workshop.id)
        .where(
            Workshop.verification_status == VerificationStatus.VERIFIED,
            MaintenanceRecord.id.in_(
                published_maintenance_select().with_only_columns(MaintenanceRecord.id)
            ),
        )
    )
    if city:
        statement = statement.where(Workshop.city.ilike(city.strip()))
    if state:
        statement = statement.where(Workshop.state == state.upper().strip())
    if category:
        statement = statement.where(MaintenanceRecord.category == category)
    grouped = {}
    for workshop, record in (await session.execute(statement)).all():
        grouped.setdefault(workshop.id, (workshop, []))[1].append(record)
    ranked, unranked = [], []
    for workshop, records in grouped.values():
        item, raw_score, _ = await workshop_metrics(session, workshop, records)
        (ranked if item.eligible_for_ranking else unranked).append((item, raw_score))
    ranked.sort(key=lambda pair: (-pair[1], -pair[0].completed_services_count, pair[0].workshop_id))
    unranked.sort(key=lambda pair: (-pair[0].completed_services_count, pair[0].workshop_id))
    return WorkshopRankingResponse(
        score_version=SCORE_VERSION,
        score_explanation=SCORE_EXPLANATION,
        items=[i for i, _ in ranked[:limit]],
        unranked_items=[i for i, _ in unranked[:limit]],
    )


async def get_workshop_performance(session, workshop_id):
    from fastapi import HTTPException

    workshop = await session.get(Workshop, workshop_id)
    if workshop is None or workshop.verification_status != VerificationStatus.VERIFIED:
        raise HTTPException(status_code=404, detail="Workshop not found")
    records = list(
        (
            await session.scalars(
                published_maintenance_select().where(MaintenanceRecord.workshop_id == workshop.id)
            )
        ).all()
    )
    metrics, _, reviews = await workshop_metrics(session, workshop, records)
    return {
        "score_version": SCORE_VERSION,
        "score_explanation": SCORE_EXPLANATION,
        "metrics": metrics,
        "reviews": [
            {"stars": r.stars, "comment": r.comment if not r.comment_hidden else None}
            for r in reviews
        ],
    }
