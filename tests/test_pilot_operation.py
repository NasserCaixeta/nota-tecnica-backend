import json
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.audit.models import AuditEvent


def pilot_settings(**changes):
    return Settings(
        _env_file=None,
        app_env="pilot",
        debug=False,
        jwt_secret_key="j" * 40,
        invitation_secret_key="i" * 40,
        recovery_secret_key="r" * 40,
        frontend_url="https://pilot.example.invalid",
        backend_cors_origins=["https://pilot.example.invalid"],
        **changes,
    )


def test_pilot_refuses_debug_default_and_shared_secrets():
    assert pilot_settings().app_env == "pilot"
    for changes in (
        {"DEBUG": True},
        {"JWT_SECRET_KEY": "change-me-in-production-use-32-bytes-min"},
        {"RECOVERY_SECRET_KEY": "j" * 40},
        {"FRONTEND_URL": "http://public.example.invalid"},
        {"BACKEND_CORS_ORIGINS": ["*"]},
    ):
        with pytest.raises(ValidationError):
            pilot_settings(**changes)


def test_configuration_cannot_select_production_payments():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, PAYMENTS_ENVIRONMENT="production")


async def test_pilot_report_empty_window_and_event_boundaries(db_session):
    from app.cli.pilot_report import build_report

    empty = await build_report(db_session, date(2026, 10, 1), date(2026, 10, 2))
    assert empty["review"]["mean_hours"] is None
    assert empty["completeness"]["stars_percent"] is None
    for action, when, metadata in [
        ("maintenance.submit", datetime(2026, 9, 30, 23, tzinfo=UTC), {"revision_id": 7}),
        (
            "maintenance.review",
            datetime(2026, 10, 1, 1, tzinfo=UTC),
            {"revision_id": 7, "decision": "rejected"},
        ),
        ("service_dispute.opened", datetime(2026, 10, 2, 23, 59, tzinfo=UTC), {}),
        ("service_dispute.opened", datetime(2026, 10, 3, tzinfo=UTC), {}),
    ]:
        db_session.add(
            AuditEvent(
                action=action,
                target_type="maintenance_record",
                target_id=99,
                event_metadata=metadata,
                created_at=when,
                reason="private-name token-secret cpf-secret",
            )
        )
    await db_session.commit()
    report = await build_report(db_session, date(2026, 10, 1), date(2026, 10, 2))
    assert report["review"] == {"samples": 1, "mean_hours": 2.0, "rejected": 1}
    assert report["events"]["disputes_opened"] == 1
    assert "private-name" not in json.dumps(report)
    assert "target_id" not in json.dumps(report)
    with pytest.raises(ValueError):
        await build_report(db_session, date(2026, 10, 2), date(2026, 10, 1))


def test_readiness_failure_hides_dependency_details(client, monkeypatch):
    import app.api.v1.health as health

    async def fail():
        raise RuntimeError("postgres://secret:password@privatehost")

    monkeypatch.setattr(health, "check_dependencies", fail, raising=False)
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_error_logs_do_not_contain_exception_payload(client, caplog, monkeypatch):
    from app.core.exceptions import logger

    # Alembic's fileConfig disables pre-existing loggers in migration tests.
    monkeypatch.setattr(logger, "disabled", False)

    @client.app.get("/private-error")
    def failure():
        raise RuntimeError("cpf-secret signed-url-secret")

    client.app.debug = False
    client.app.middleware_stack = None
    # TestClient's transport owns this flag.
    client._transport.raise_server_exceptions = False
    assert client.get("/private-error").status_code == 500
    assert "Unexpected application error" in caplog.text
    assert "cpf-secret" not in caplog.text


async def test_report_cohort_uses_canonical_publication_and_exact_revision(client, db_session):
    from app.cli.pilot_report import build_report
    from app.modules.maintenance.models import MaintenanceRecord
    from app.modules.ranking.models import ServiceReview
    from tests.test_maintenance_moderation import approve_customer_service

    _, _, data, _, _, _ = await approve_customer_service(client, db_session)
    record = await db_session.get(MaintenanceRecord, data["id"])
    record.entry_date = date(2026, 6, 1)
    record.promised_delivery_date = date(2026, 6, 2)
    record.actual_delivery_date = date(2026, 6, 2)
    db_session.add(
        ServiceReview(
            record_id=record.id,
            revision_id=record.current_revision_id,
            customer_user_id=record.author_user_id,
            stars=5,
        )
    )
    await db_session.commit()
    today = datetime.now(UTC).date()
    report = await build_report(db_session, today, today)
    assert report["cohort_current_state"]["services_created"] == 1
    assert report["completeness"] == {
        "published_sample": 1,
        "with_deadlines": 1,
        "with_stars": 1,
        "deadlines_percent": 100.0,
        "stars_percent": 100.0,
    }
    assert report["review"]["samples"] == 1
    record.dispute_open = True
    await db_session.commit()
    report = await build_report(db_session, today, today)
    assert report["cohort_current_state"]["services_created"] == 1
    assert report["completeness"]["published_sample"] == 0
