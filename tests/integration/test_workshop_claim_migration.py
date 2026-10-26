import asyncio

import pytest
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.core.config import get_settings
from app.modules.documents.models import (
    Document,
    DocumentProcessingStatus,
    DocumentReviewStatus,
    DocumentType,
    DocumentUploadStatus,
)
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
            data = dict(
                owner_user_id=actor.id,
                workshop_claim_id=claim.id,
                document_type=DocumentType.OTHER,
                file_name="proof.pdf",
                original_file_name="proof.pdf",
                content_type="application/pdf",
                review_status=DocumentReviewStatus.PENDING,
                upload_status=DocumentUploadStatus.PENDING,
                processing_status=DocumentProcessingStatus.NOT_REQUESTED,
            )
            valid = Document(**data, storage_key="valid-proof", vehicle_id=None)
            session.add(valid)
            await session.commit()
            assert valid.workshop_claim_id == claim.id
            with pytest.raises(IntegrityError, match="ck_document_subject"):
                async with session.begin_nested():
                    session.add(
                        Document(**data, storage_key="invalid-proof", vehicle_id=vehicle.id)
                    )
                    await session.flush()
    finally:
        get_settings.cache_clear()
