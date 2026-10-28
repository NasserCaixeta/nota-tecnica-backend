import asyncio

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.core.config import get_settings
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
        from datetime import date

        from tests.integration.legacy_fixtures import insert_legacy_row
        from tests.test_auth_users import user_payload

        async with pg_engine.begin() as session:
            user = user_payload()
            user.pop("password")
            user.update(
                password_hash="unused",
                cpf="52998224725",
                birth_date=date(1990, 1, 20),
                profile_type="CUSTOMER",
            )
            actor_id = await insert_legacy_row(session, "users", user)
            from app.modules.workshops.schemas import WorkshopCreate

            workshop = WorkshopCreate(**workshop_payload(source="owner_claimed")).model_dump()
            workshop.update(verification_status="PENDING", submitted_by_user_id=actor_id)
            workshop_id = await insert_legacy_row(session, "workshops", workshop)
            claim_id = await insert_legacy_row(
                session, "workshop_claims", {"workshop_id": workshop_id, "user_id": actor_id}
            )
            vehicle_id = await insert_legacy_row(session, "vehicles", vehicle_payload())
            insert = text("""INSERT INTO documents
                (owner_user_id,workshop_claim_id,vehicle_id,document_type,file_name,
                 original_file_name,content_type,storage_key,review_status,upload_status,
                 processing_status,created_at,updated_at)
                VALUES (:owner,:claim,:vehicle,'OTHER','proof.pdf','proof.pdf',
                'application/pdf',:key,'PENDING','PENDING','NOT_REQUESTED',now(),now())
                RETURNING workshop_claim_id""")
            params = dict(owner=actor_id, claim=claim_id, vehicle=None, key="valid-proof")
            result = await session.execute(insert, params)
            assert result.scalar_one() == claim_id
            with pytest.raises(IntegrityError, match="ck_document_subject"):
                async with session.begin_nested():
                    await session.execute(
                        insert, {**params, "vehicle": vehicle_id, "key": "invalid-proof"}
                    )
    finally:
        get_settings.cache_clear()
