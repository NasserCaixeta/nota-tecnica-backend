import asyncio
from datetime import date

import pytest
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from alembic import command
from app.core.config import get_settings
from app.modules.documents.models import Document, DocumentReviewStatus
from app.modules.maintenance.models import MaintenanceRevision
from app.modules.maintenance.publication import published_maintenance_select
from app.modules.users.models import ParticipationStatus, User
from tests.integration.legacy_fixtures import insert_legacy_row
from tests.test_auth_users import user_payload
from tests.test_vehicles import vehicle_payload


@pytest.mark.parametrize("legacy", [False, True])
async def test_full_migration_chain_preserves_legacy_data_and_matches_models(
    pg_url, pg_engine, monkeypatch, legacy
):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    get_settings.cache_clear()
    config = Config("alembic.ini")
    try:
        if legacy:
            await asyncio.to_thread(command.upgrade, config, "20260707_0004")
            async with pg_engine.begin() as conn:
                data = user_payload()
                data.pop("password")
                data.update(
                    password_hash="unused",
                    cpf="52998224725",
                    birth_date=date(1990, 1, 20),
                    profile_type="customer",
                )
                user_id = await insert_legacy_row(conn, "users", data)
                vehicle_id = await insert_legacy_row(conn, "vehicles", vehicle_payload())
                await conn.execute(
                    text("""INSERT INTO vehicle_users
                    (user_id,vehicle_id,relationship_type,verification_status,garage_status,review_attempts,requested_document_types,created_at,updated_at)
                    VALUES (:u,:v,'OWNER','VERIFIED','ACTIVE',0,'[]',now(),now())"""),
                    {"u": user_id, "v": vehicle_id},
                )
                await conn.execute(
                    text("""INSERT INTO maintenance_records
                    (vehicle_id,author_user_id,service_date,odometer,category,vehicle_system,description,labor_cost,parts_cost,total_cost,status,created_at,updated_at)
                    VALUES (:v,:u,'2026-06-15',50000,'MECHANICAL','ENGINE','Legacy private',
                    120,180,300,'COMPLETED',now(),now())"""),
                    {"u": user_id, "v": vehicle_id},
                )
                await conn.execute(
                    text("""INSERT INTO documents
                    (owner_user_id,vehicle_id,document_type,file_name,content_type,storage_key,review_status,upload_status,processing_status,original_file_name,created_at,updated_at)
                    VALUES (:u,:v,'CRLV','legacy.pdf','application/pdf','legacy-private',
                    'APPROVED','UPLOADED','NOT_REQUESTED','legacy.pdf',now(),now())"""),
                    {"u": user_id, "v": vehicle_id},
                )
        await asyncio.to_thread(command.upgrade, config, "head")
        await asyncio.to_thread(command.check, config)
        async with async_sessionmaker(pg_engine)() as session:
            assert list(await session.scalars(published_maintenance_select())) == []
            if legacy:
                user = await session.scalar(select(User))
                assert (
                    user.auth_version == 1
                    and user.participation_status == ParticipationStatus.PENDING
                )
                document = await session.scalar(select(Document))
                assert document.review_status == DocumentReviewStatus.APPROVED
                assert document.storage_verified is False
                revision = await session.scalar(select(MaintenanceRevision))
                assert revision.admin_status == "pending" and revision.editorial_status == "draft"
    finally:
        get_settings.cache_clear()
