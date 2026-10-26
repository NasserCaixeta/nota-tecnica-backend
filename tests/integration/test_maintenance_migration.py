import asyncio
from datetime import date

from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.core.config import get_settings
from app.modules.maintenance.publication import published_maintenance_select
from app.modules.users.models import User, UserProfileType
from tests.test_auth_users import user_payload


async def test_legacy_completed_record_becomes_private_pending_revision(
    pg_url, pg_engine, monkeypatch
):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    get_settings.cache_clear()
    try:
        config = Config("alembic.ini")
        await asyncio.to_thread(command.upgrade, config, "20261021_0007")
        async with pg_engine.begin() as conn:
            data = user_payload()
            data.pop("password")
            data.update(
                password_hash="unused",
                cpf="52998224725",
                birth_date=date(1990, 1, 20),
                profile_type=UserProfileType.CUSTOMER,
            )
            await conn.execute(User.__table__.insert().values(**data))
            await conn.execute(
                text("""INSERT INTO vehicles
                (id,plate,brand,model,model_year,color,vehicle_type,chassis,renavam,fuel_type,
                 engine,transmission,created_at,updated_at)
                VALUES (1,'ABC1D23','VW','Gol',2020,'Prata','Carro','legacy-vin','legacy-renavam',
                'Gasolina','1.0','Manual',now(),now())""")
            )
            await conn.execute(
                text("""INSERT INTO maintenance_records
                (id,vehicle_id,author_user_id,service_date,odometer,category,vehicle_system,
                 description,labor_cost,parts_cost,total_cost,status,created_at,updated_at)
                VALUES (1,1,1,'2026-06-15',50000,'MECHANICAL','ENGINE','Legacy private data',
                120,180,300,'COMPLETED',now(),now())""")
            )
        await asyncio.to_thread(command.upgrade, config, "20261021_0008")
        async with pg_engine.connect() as conn:
            assert (await conn.execute(published_maintenance_select())).all() == []
            row = (await conn.execute(text("SELECT * FROM maintenance_revisions"))).mappings().one()
            assert row["editorial_status"] == "draft"
            assert row["admin_status"] == "pending"
            assert row["snapshot"]["labor_cost"] == "120.00"
            assert row["snapshot"]["description"] == "Legacy private data"
            assert (
                await conn.execute(text("SELECT current_revision_id FROM maintenance_records"))
            ).scalar() == row["id"]
            assert (
                await conn.execute(text("SELECT count(*) FROM maintenance_records"))
            ).scalar() == 1
        # A reference with only a plate must be storable without fabricated identifiers.
        async with pg_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO vehicles (id,plate,created_at,updated_at) "
                    "VALUES (2,'XYZ9A87',now(),now())"
                )
            )
            assert (
                await conn.execute(text("SELECT chassis FROM vehicles WHERE plate='XYZ9A87'"))
            ).scalar() is None
    finally:
        get_settings.cache_clear()
