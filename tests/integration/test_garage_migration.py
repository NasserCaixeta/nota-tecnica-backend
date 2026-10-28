import asyncio
from datetime import date

from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.core.config import get_settings
from app.modules.users.models import UserProfileType
from app.modules.vehicles.models import (
    Vehicle,
)
from tests.integration.legacy_fixtures import insert_legacy_row
from tests.test_auth_users import user_payload
from tests.test_vehicles import vehicle_payload


async def test_garage_migration_preserves_links_with_only_one_free_vehicle(
    pg_url,
    pg_engine,
    monkeypatch,
):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    get_settings.cache_clear()
    try:
        config = Config("alembic.ini")
        await asyncio.to_thread(command.upgrade, config, "20261021_0005")
        user = user_payload()
        user.pop("password")
        user.update(
            cpf="52998224725",
            password_hash="unused",
            birth_date=date(1990, 1, 20),
            profile_type=UserProfileType.CUSTOMER,
        )
        async with pg_engine.begin() as conn:
            await insert_legacy_row(conn, "users", user)
            for index, plate in enumerate(["ABC1D23", "DEF2E34"]):
                result = await conn.execute(
                    Vehicle.__table__.insert()
                    .values(
                        **vehicle_payload(
                            plate=plate, chassis=f"legacy-{index}", renavam=f"1234567890{index}"
                        )
                    )
                    .returning(Vehicle.id)
                )
                vehicle_id = result.scalar_one()
                await conn.execute(
                    text("""INSERT INTO vehicle_users
                    (user_id,vehicle_id,relationship_type,verification_status,garage_status,
                     review_attempts,requested_document_types,created_at,updated_at)
                    VALUES (1,:vehicle_id,'OWNER','PENDING',:garage_status,0,'[]',now(),now())"""),
                    {
                        "vehicle_id": vehicle_id,
                        "garage_status": "PENDING_DOCUMENTS" if index == 0 else "PAYMENT_REQUIRED",
                    },
                )
        await asyncio.to_thread(command.upgrade, config, "20261021_0006")
        async with pg_engine.connect() as conn:
            assert (
                await conn.execute(text("SELECT count(*) FROM garage_memberships"))
            ).scalar() == 2
            assert (
                await conn.execute(text("SELECT free_garage_vehicle_id FROM users"))
            ).scalar() == 1
            states = (
                (await conn.execute(text("SELECT garage_status FROM vehicle_users")))
                .scalars()
                .all()
            )
            assert states == ["PENDING_DOCUMENTS", "PENDING_DOCUMENTS"]
        async with pg_engine.begin() as conn:
            await conn.execute(
                text("""INSERT INTO documents
                (owner_user_id,vehicle_id,document_type,file_name,content_type,storage_key,
                 review_status,upload_status,processing_status,original_file_name,created_at,updated_at)
                VALUES (1,1,'CRLV','legacy.pdf','application/pdf','legacy-key','APPROVED',
                        'UPLOADED','NOT_REQUESTED','legacy.pdf',now(),now())""")
            )
        await asyncio.to_thread(command.upgrade, config, "20261021_0006b")
        async with pg_engine.connect() as conn:
            assert (
                await conn.execute(text("SELECT storage_verified FROM documents"))
            ).scalar() is False
    finally:
        get_settings.cache_clear()
