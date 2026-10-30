"""Backup roundtrip in newly created, exclusively named local test databases."""

import asyncio
import os
import subprocess
from datetime import date
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.core.config import get_settings
from tests.integration.legacy_fixtures import insert_legacy_row
from tests.test_auth_users import user_payload
from tests.test_vehicles import vehicle_payload


async def main():
    url = make_url(os.environ["TEST_POSTGRES_URL"])
    if url.host not in {"localhost", "127.0.0.1"} or not (url.database or "").endswith("_test"):
        raise RuntimeError("Backup validation requires local disposable test infrastructure")
    suffix = uuid4().hex[:10]
    source_name = f"nota_tecnica_backup_source_{suffix}_test"
    target_name = f"nota_tecnica_backup_restore_{suffix}_test"
    admin = create_async_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        for database in (source_name, target_name):
            if await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database}
            ):
                raise RuntimeError("Refusing to reuse any existing backup-validation database")
        for database in (source_name, target_name):
            await conn.execute(text(f'CREATE DATABASE "{database}"'))
    await admin.dispose()
    source = create_async_engine(url.set(database=source_name))
    target = create_async_engine(url.set(database=target_name))
    os.environ["DATABASE_URL"] = url.set(database=source_name).render_as_string(hide_password=False)
    get_settings.cache_clear()
    await asyncio.to_thread(command.upgrade, Config("alembic.ini"), "head")
    async with source.begin() as conn:
        data = user_payload(email="backup-probe@example.com")
        data.pop("password")
        data.update(
            password_hash="synthetic-unused-hash",
            cpf="52998224725",
            birth_date=date(1990, 1, 20),
            profile_type="CUSTOMER",
        )
        user_id = await insert_legacy_row(conn, "users", data)
        vehicle_id = await insert_legacy_row(conn, "vehicles", vehicle_payload(plate="ABC1D23"))
        await insert_legacy_row(
            conn,
            "documents",
            {
                "owner_user_id": user_id,
                "vehicle_id": vehicle_id,
                "document_type": "CRLV",
                "file_name": "synthetic.pdf",
                "original_file_name": "synthetic.pdf",
                "content_type": "application/pdf",
                "storage_key": "synthetic-backup-proof",
                "review_status": "PENDING",
                "upload_status": "PENDING",
                "processing_status": "NOT_REQUESTED",
            },
        )
        await insert_legacy_row(
            conn,
            "audit_events",
            {
                "actor_id": None,
                "action": "backup.validation",
                "target_type": "user",
                "target_id": user_id,
                "version": 1,
                "reason": "synthetic_fixture",
                "metadata": {},
            },
        )
    dump = (
        Path(f"/private/tmp/nota-tecnica-backup-{suffix}.dump")
        if Path("/private/tmp").exists()
        else Path(f"/tmp/nota-tecnica-backup-{suffix}.dump")
    )
    container = os.environ.get("POSTGRES_CONTAINER", "nota-tecnica-piloto-postgres-1")
    with dump.open("xb") as output:
        subprocess.run(
            ["docker", "exec", container, "pg_dump", "-U", url.username, "-Fc", source_name],
            stdout=output,
            check=True,
        )
    with dump.open("rb") as source_file:
        subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                container,
                "pg_restore",
                "-U",
                url.username,
                "--no-owner",
                "--exit-on-error",
                "-d",
                target_name,
            ],
            stdin=source_file,
            check=True,
        )
    async with target.connect() as conn:
        for table in ("users", "documents", "audit_events"):
            assert await conn.scalar(text(f"SELECT count(*) FROM {table}")) == 1
        assert await conn.scalar(text("SELECT auth_version FROM users")) == 1
        assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == "20261030_0018"
    await source.dispose()
    await target.dispose()
    print(
        "Backup restored: head0018, synthetic user/document/audit preserved; "
        "external storage excluded."
    )


if __name__ == "__main__":
    asyncio.run(main())
