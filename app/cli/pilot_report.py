"""Aggregate operational metrics; never emit identities, reasons or provider payloads."""

import argparse
import asyncio
import json
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select

from app.db.session import get_async_session_factory
from app.modules.audit.models import AuditEvent
from app.modules.maintenance.models import MaintenanceRecord
from app.modules.maintenance.publication import published_maintenance_select
from app.modules.payments.models import PaymentOrder
from app.modules.ranking.models import ServiceReview
from app.modules.users.models import User
from app.modules.vehicles.models import VehicleUser
from app.modules.workshops.models import Workshop


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def build_report(session, start: date, end: date):
    if start > end:
        raise ValueError("Start must precede end")
    lower = datetime.combine(start, time.min, UTC)
    upper = datetime.combine(end + timedelta(days=1), time.min, UTC)

    def window(column):
        return (column >= lower, column < upper)

    async def count(model, *where):
        return await session.scalar(select(func.count()).select_from(model).where(*where))

    # Cohort metrics are current state of entities created in the UTC window,
    # not an invented historical snapshot of their status at end-of-window.
    cohort = published_maintenance_select().where(*window(MaintenanceRecord.created_at)).subquery()
    published = await session.scalar(select(func.count()).select_from(cohort))
    deadlines = await session.scalar(
        select(func.count())
        .select_from(cohort)
        .where(
            cohort.c.entry_date.is_not(None),
            cohort.c.promised_delivery_date.is_not(None),
            cohort.c.actual_delivery_date.is_not(None),
        )
    )
    stars = await session.scalar(
        select(func.count())
        .select_from(cohort)
        .join(
            ServiceReview,
            (ServiceReview.record_id == cohort.c.id)
            & (ServiceReview.revision_id == cohort.c.current_revision_id),
        )
    )

    # Only structural audit columns are read; reasons and metadata other than
    # the allowlisted revision/decision keys never enter the output.
    events = (
        await session.execute(
            select(
                AuditEvent.action,
                AuditEvent.target_id,
                AuditEvent.event_metadata,
                AuditEvent.created_at,
            )
            .where(AuditEvent.created_at < upper)
            .order_by(AuditEvent.created_at, AuditEvent.id)
        )
    ).all()
    submissions, durations, rejected = {}, [], 0
    event_counts = {"submissions": 0, "duplicates_associated": 0, "disputes_opened": 0}
    action_keys = {
        "maintenance.submit": "submissions",
        "maintenance.associated": "duplicates_associated",
        "service_dispute.opened": "disputes_opened",
    }
    for action, target, metadata, when in events:
        when = utc(when)
        revision = metadata.get("revision_id")
        key = (target, revision)
        if action == "maintenance.submit" and revision is not None:
            submissions[key] = when
        submitted = submissions.pop(key, None) if action == "maintenance.review" else None
        if when < lower:
            continue
        if action in action_keys:
            event_counts[action_keys[action]] += 1
        if action == "maintenance.review":
            rejected += metadata.get("decision") == "rejected"
            if submitted is not None:
                durations.append((when - submitted).total_seconds() / 3600)
    orders = dict(
        (
            await session.execute(
                select(PaymentOrder.state, func.count())
                .where(*window(PaymentOrder.created_at), PaymentOrder.environment == "sandbox")
                .group_by(PaymentOrder.state)
            )
        ).all()
    )
    return {
        "window_utc": {"from": start.isoformat(), "to_inclusive": end.isoformat()},
        "cohort_current_state": {
            "participants_created": await count(User, *window(User.created_at)),
            "vehicle_links_created": await count(VehicleUser, *window(VehicleUser.created_at)),
            "workshops_created": await count(Workshop, *window(Workshop.created_at)),
            "services_created": await count(
                MaintenanceRecord, *window(MaintenanceRecord.created_at)
            ),
            "services_published_now": published,
            "participants_approved_now": await count(
                User, *window(User.created_at), User.participation_status == "approved"
            ),
        },
        "events": event_counts,
        "review": {
            "samples": len(durations),
            "mean_hours": round(sum(durations) / len(durations), 2) if durations else None,
            "rejected": rejected,
        },
        "completeness": {
            "published_sample": published,
            "with_deadlines": deadlines,
            "with_stars": stars,
            "deadlines_percent": round(100 * deadlines / published, 2) if published else None,
            "stars_percent": round(100 * stars / published, 2) if published else None,
        },
        "sandbox_orders_by_state": orders,
    }


async def run(start, end):
    async with get_async_session_factory()() as session:
        return await build_report(session, start, end)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="start", type=date.fromisoformat, required=True)
    parser.add_argument("--to", dest="end", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    if args.start > args.end:
        parser.error("Start must precede end")
    print(json.dumps(asyncio.run(run(args.start, args.end)), indent=2))


if __name__ == "__main__":
    main()
