import asyncio

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command


@pytest.mark.parametrize("profile", ["ADMIN", "admin", "CUSTOMER", "customer"])
async def test_identity_migration_preserves_data_without_promoting_customers(
    pg_url, pg_engine, monkeypatch, profile
):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        config = Config("alembic.ini")
        await asyncio.to_thread(command.upgrade, config, "20260707_0004")
        async with pg_engine.begin() as conn:
            await conn.execute(
                text("""
                INSERT INTO users (full_name,email,password_hash,cpf,phone,birth_date,
                  profile_type,zip_code,street,number,neighborhood,city,state,is_active,
                  created_at,updated_at)
                VALUES ('Legacy','legacy@example.com','hash','52998224725','11',
                  '1990-01-01',:profile,'01001000','Central','1','Centro','SP','SP',true,
                  now(),now())
            """),
                {"profile": profile},
            )
        await asyncio.to_thread(command.upgrade, config, "20261021_0005")
        async with pg_engine.connect() as conn:
            row = (
                (await conn.execute(text("SELECT email,is_admin,participation_status FROM users")))
                .mappings()
                .one()
            )
        assert row["email"] == "legacy@example.com"
        assert row["is_admin"] is (profile.lower() == "admin")
        assert row["participation_status"] == (
            "approved" if profile.lower() == "admin" else "pending"
        )
    finally:
        get_settings.cache_clear()
