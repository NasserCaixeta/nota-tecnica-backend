import asyncio

import pytest
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.core.config import get_settings
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from app.modules.workshops.models import WorkshopClaim
from app.modules.workshops.schemas import WorkshopCreate
from app.modules.workshops.service import create_workshop_for_user
from tests.integration.test_admin_concurrency import prepare_users
from tests.test_vehicles import vehicle_payload
from tests.test_workshops import workshop_payload


async def test_claim_migration_accepts_private_evidence_with_a_single_subject(
    pg_url,
    pg_engine,
    monkeypatch,
):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    get_settings.cache_clear()
    try:
        await asyncio.to_thread(command.upgrade, Config("alembic.ini"), "20261021_0007")
        factory = await prepare_users(pg_engine)
        async with factory() as session:
            actor = await session.get(User, 1)
            await create_workshop_for_user(
                session, WorkshopCreate(**workshop_payload(source="owner_claimed")), actor
            )
            claim = await session.scalar(select(WorkshopClaim))
            vehicle = Vehicle(**vehicle_payload())
            session.add(vehicle)
            await session.flush()
            insert = text("""INSERT INTO documents
                (owner_user_id,workshop_claim_id,vehicle_id,document_type,file_name,
                 original_file_name,content_type,storage_key,review_status,upload_status,
                 processing_status,created_at,updated_at)
                VALUES (:owner,:claim,:vehicle,'OTHER','proof.pdf','proof.pdf',
                'application/pdf',:key,'PENDING','PENDING','NOT_REQUESTED',now(),now())
                RETURNING workshop_claim_id""")
            params = dict(owner=actor.id, claim=claim.id, vehicle=None, key="valid-proof")
            result = await session.execute(insert, params)
            assert result.scalar_one() == claim.id
            await session.commit()
            with pytest.raises(IntegrityError, match="ck_document_subject"):
                async with session.begin_nested():
                    await session.execute(
                        insert, {**params, "vehicle": vehicle.id, "key": "invalid-proof"}
                    )
    finally:
        get_settings.cache_clear()
