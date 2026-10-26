import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.modules.audit.models import AuditEvent
from app.modules.documents.models import (
    Document,
    DocumentProcessingStatus,
    DocumentReviewStatus,
    DocumentType,
    DocumentUploadStatus,
)
from app.modules.garage.creation import create_garage_vehicle_link
from app.modules.garage.schemas import GarageVehicleCreate
from app.modules.maintenance.models import MaintenanceRevision
from app.modules.maintenance.moderation import review_maintenance
from app.modules.maintenance.schemas import MaintenanceRecordCreate, MaintenanceReview
from app.modules.maintenance.service import create_maintenance_record
from app.modules.users.models import User
from tests.integration.test_admin_concurrency import prepare_users
from tests.test_maintenance import maintenance_payload
from tests.test_vehicles import vehicle_payload


async def prepare_service(engine):
    factory = await prepare_users(engine)
    async with factory() as session:
        user = await session.get(User, 3)
        vehicle, _ = await create_garage_vehicle_link(
            session, GarageVehicleCreate(**vehicle_payload()), user
        )
        record = await create_maintenance_record(
            session, vehicle.id, MaintenanceRecordCreate(**maintenance_payload()), user
        )
        revision = await session.get(MaintenanceRevision, record.current_revision_id)
        revision.editorial_status = "submitted"
        session.add(
            Document(
                owner_user_id=3,
                vehicle_id=vehicle.id,
                maintenance_record_id=record.id,
                maintenance_revision_id=revision.id,
                document_type=DocumentType.INVOICE,
                storage_key="verified/proof",
                file_name="proof.pdf",
                original_file_name="proof.pdf",
                content_type="application/pdf",
                storage_verified=True,
                review_status=DocumentReviewStatus.APPROVED,
                upload_status=DocumentUploadStatus.UPLOADED,
                processing_status=DocumentProcessingStatus.NOT_REQUESTED,
            )
        )
        await session.commit()
        return factory, record.id, revision.id


async def test_two_service_reviewers_cannot_overwrite_the_same_version(pg_engine):
    factory, record_id, revision_id = await prepare_service(pg_engine)
    payload = MaintenanceReview(
        expected_version=1,
        revision_id=revision_id,
        decision="approved",
        reason="Inspected",
        public_description="Troca de óleo",
    )

    async def review(actor_id):
        async with factory() as session:
            actor = await session.get(User, actor_id)
            try:
                await review_maintenance(session, record_id, payload, actor)
                return 200
            except HTTPException as exc:
                await session.rollback()
                return exc.status_code

    assert sorted(await asyncio.gather(review(1), review(2))) == [200, 409]
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "maintenance.review")
            )
            == 1
        )


async def test_failed_audit_rolls_back_service_decision(pg_engine, monkeypatch):
    factory, record_id, revision_id = await prepare_service(pg_engine)

    async def fail_audit(*args, **kwargs):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr("app.modules.maintenance.moderation.append_audit", fail_audit)
    async with factory() as session:
        actor = await session.get(User, 1)
        with pytest.raises(RuntimeError, match="Audit unavailable"):
            await review_maintenance(
                session,
                record_id,
                MaintenanceReview(
                    expected_version=1,
                    revision_id=revision_id,
                    decision="approved",
                    reason="Inspected",
                    public_description="Troca de óleo",
                ),
                actor,
            )
        await session.rollback()
    async with factory() as session:
        revision = await session.get(MaintenanceRevision, revision_id)
        assert revision.admin_status == "pending"
        assert revision.review_version == 1
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "maintenance.review")
            )
            == 0
        )


async def test_two_customer_confirmations_create_one_acknowledgement(pg_engine):
    from app.modules.maintenance.acknowledgements import acknowledge_service
    from app.modules.vehicles.models import GarageValidationStatus, VehicleUser, VerificationStatus

    factory, record_id, revision_id = await prepare_service(pg_engine)
    async with factory() as session:
        revision = await session.get(MaintenanceRevision, revision_id)
        revision.customer_acknowledgement = "awaiting_customer"
        link = await session.scalar(select(VehicleUser).where(VehicleUser.user_id == 3))
        link.verification_status = VerificationStatus.VERIFIED
        link.garage_status = GarageValidationStatus.ACTIVE
        await session.commit()

    async def confirm():
        async with factory() as session:
            actor = await session.get(User, 3)
            await acknowledge_service(session, record_id, revision_id, actor)

    await asyncio.gather(confirm(), confirm())
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "maintenance.acknowledge")
            )
            == 1
        )


async def test_concurrent_dispute_decisions_do_not_override_customer_refusal(pg_engine):
    from app.modules.maintenance.disputes import open_dispute, review_dispute
    from app.modules.maintenance.models import MaintenanceRecord
    from app.modules.maintenance.schemas import ServiceDisputeCreate, ServiceDisputeReview
    from app.modules.vehicles.models import GarageValidationStatus, VehicleUser, VerificationStatus

    factory, record_id, revision_id = await prepare_service(pg_engine)
    async with factory() as session:
        actor = await session.get(User, 3)
        link = await session.scalar(select(VehicleUser).where(VehicleUser.user_id == 3))
        link.verification_status = VerificationStatus.VERIFIED
        link.garage_status = GarageValidationStatus.ACTIVE
        await session.commit()
        dispute = await open_dispute(
            session,
            record_id,
            ServiceDisputeCreate(revision_id=revision_id, reason="Wrong parts"),
            actor,
        )
        dispute_id = dispute.id

    async def decide(actor_id):
        async with factory() as session:
            actor = await session.get(User, actor_id)
            try:
                await review_dispute(
                    session,
                    dispute_id,
                    ServiceDisputeReview(
                        expected_version=1, resolution="resolved", reason="Review concluded"
                    ),
                    actor,
                )
                return 200
            except HTTPException as exc:
                await session.rollback()
                return exc.status_code

    assert sorted(await asyncio.gather(decide(1), decide(2))) == [200, 409]
    async with factory() as session:
        revision = await session.get(MaintenanceRevision, revision_id)
        record = await session.get(MaintenanceRecord, record_id)
        assert revision.customer_acknowledgement == "disputed"
        assert record.dispute_open is False
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "service_dispute.reviewed")
            )
            == 1
        )
