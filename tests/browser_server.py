"""Isolated HTTP acceptance fixture. Never import this from production entrypoints."""

import asyncio
import hashlib
import os
from calendar import monthrange
from datetime import UTC, datetime
from urllib.parse import quote
from uuid import uuid4

from sqlalchemy.engine import make_url

TARGET = os.environ.get("E2E_DATABASE_URL", "")
parsed = make_url(TARGET) if TARGET else None
if (
    os.environ.get("E2E_TEST_RUN") != "1"
    or parsed is None
    or parsed.host not in {"localhost", "127.0.0.1"}
    or not (parsed.database or "").endswith("_test")
):
    raise RuntimeError(
        "Browser fixtures require an explicitly enabled local disposable *_test database"
    )
for key, value in {
    "DATABASE_URL": TARGET,
    "REDIS_URL": os.environ.get("E2E_REDIS_URL", "redis://localhost:55440/15"),
    "APP_ENV": "test",
    "DEBUG": "false",
    "FRONTEND_URL": "http://127.0.0.1:5179",
    "BACKEND_CORS_ORIGINS": '["http://127.0.0.1:5179"]',
    "JWT_SECRET_KEY": "browser-fixture-only-jwt-key-at-least-32-characters",
    "INVITATION_SECRET_KEY": "browser-fixture-only-invitation-key-at-least-32-characters",
    "RECOVERY_SECRET_KEY": "browser-fixture-only-recovery-key-at-least-32-characters",
    "PAYMENTS_ENABLED": "true",
    "PAYMENTS_HISTORY_PRICE_CENTS": "1900",
    "PAYMENTS_SUBSCRIPTION_PRICE_CENTS": "4900",
    "PAYMENTS_CALLBACK_BASE_URL": "https://e2e.invalid",
    "ASAAS_API_KEY": "browser-fixture-only",
    "ASAAS_WEBHOOK_TOKEN": "browser-fixture-only-webhook-token-at-least-32-characters",
    "SMTP_ENABLED": "false",
    "REGISTER_RATE_LIMIT": "1000",
    "LOGIN_IP_RATE_LIMIT": "1000",
    "LOGIN_IDENTITY_RATE_LIMIT": "1000",
    "QUERY_RATE_LIMIT": "1000",
    "INVITATION_RATE_LIMIT": "1000",
}.items():
    os.environ[key] = value

import uvicorn  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi import HTTPException, Request, Response  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import dispose_engine, get_async_session_factory, get_engine  # noqa: E402
from app.integrations.storage.r2 import (  # noqa: E402
    PresignedUpload,
    StoredObjectInfo,
    sniff_content_type,
)
from app.main import create_app  # noqa: E402
from app.modules.documents.models import (  # noqa: E402
    Document,
    DocumentProcessingStatus,
    DocumentReviewStatus,
    DocumentType,
    DocumentUploadStatus,
)
from app.modules.documents.router import get_storage_client  # noqa: E402
from app.modules.garage.router import get_storage_client as garage_storage  # noqa: E402
from app.modules.maintenance.models import MaintenanceRevision  # noqa: E402
from app.modules.maintenance.moderation import review_maintenance, submit_maintenance  # noqa: E402
from app.modules.maintenance.schemas import (  # noqa: E402
    MaintenanceRecordCreate,
    MaintenanceReview,
    MaintenanceSubmit,
)
from app.modules.maintenance.service import create_maintenance_record  # noqa: E402
from app.modules.payments import webhooks  # noqa: E402
from app.modules.payments.events import process_payment_event  # noqa: E402
from app.modules.payments.gateway import CheckoutSession, ProviderPayment  # noqa: E402
from app.modules.payments.models import PaymentOrder  # noqa: E402
from app.modules.payments.router import get_payment_gateway  # noqa: E402
from app.modules.users.models import ParticipationStatus, User  # noqa: E402
from app.modules.users.schemas import UserCreate  # noqa: E402
from app.modules.users.service import create_user  # noqa: E402
from app.modules.vehicles.models import (  # noqa: E402
    GarageMembership,
    GarageValidationStatus,
    Vehicle,
    VehicleRelationshipType,
    VehicleUser,
    VerificationStatus,
)
from app.modules.workshops.models import (  # noqa: E402
    Workshop,
    WorkshopSource,
    WorkshopUser,
    WorkshopUserRole,
)
from app.modules.workshops.schemas import WorkshopCreate  # noqa: E402
from tests.test_auth_users import user_payload  # noqa: E402
from tests.test_maintenance import maintenance_payload  # noqa: E402
from tests.test_vehicles import vehicle_payload  # noqa: E402
from tests.test_workshops import workshop_payload  # noqa: E402


class MemoryStorage:
    def __init__(self):
        self.objects = {}
        self.urls = {}

    def url(self, key):
        nonce = uuid4().hex
        self.urls[nonce] = key
        return f"http://127.0.0.1:8009/__fixture-storage/{quote(key, safe='/')}?access={nonce}"

    def create_presigned_upload_url(self, storage_key, content_type, expires_seconds):
        return PresignedUpload(self.url(storage_key), {"Content-Type": content_type})

    def inspect_object(self, storage_key):
        key = storage_key
        if key not in self.objects:
            return StoredObjectInfo(False)
        data = self.objects[key]
        return StoredObjectInfo(
            True, len(data), sniff_content_type(data[:16]), hashlib.sha256(data).hexdigest()
        )

    def finalize_upload(self, storage_key, etag):
        key = storage_key
        if self.inspect_object(key).etag != etag:
            raise RuntimeError("Fixture upload changed")
        final = "verified/" + uuid4().hex
        self.objects[final] = self.objects[key]
        return final

    def create_presigned_download_url(self, storage_key, expires_seconds):
        return self.url(storage_key)


storage = MemoryStorage()


class FixtureGateway:
    async def create_checkout(self, order):
        return CheckoutSession(
            "checkout-" + order.id,
            "https://sandbox.asaas.com/checkoutSession/show?id=fixture-" + order.id,
        )

    async def reconcile_checkout(self, order):
        return await self.create_checkout(order)

    async def cancel_subscription(self, subscription_id):
        return True

    async def fetch_payment(self, provider_payment_id):
        order_id = provider_payment_id.removeprefix("pay-")
        async with get_async_session_factory()() as session:
            order = await session.get(PaymentOrder, order_id)
            if order is None:
                raise RuntimeError("Unknown fixture order")
            buyer = await session.get(User, order.buyer_id)
            start = order.created_at
            year, month = (
                (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
            )
            end = start.replace(
                year=year, month=month, day=min(start.day, monthrange(year, month)[1])
            )
            return ProviderPayment(
                id=provider_payment_id,
                state="CONFIRMED",
                order_reference=order.id,
                amount_cents=order.amount_cents,
                currency="BRL",
                customer_id="fixture-payer",
                customer_cpf=buyer.cpf,
                customer_email=buyer.email,
                checkout_id="checkout-" + order.id,
                confirmed_at=order.created_at,
                subscription_id="subscription-" + order.id
                if order.product == "garage_monthly"
                else None,
                period_starts_at=start,
                period_ends_at=end,
            )


gateway = FixtureGateway()


async def prepare():
    get_settings.cache_clear()
    async with get_engine().begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await dispose_engine()
    await asyncio.to_thread(command.upgrade, Config("alembic.ini"), "head")
    async with get_async_session_factory()() as session:
        people = []
        for email, cpf in [
            ("admin@example.com", "93541134780"),
            ("driver@example.com", "52998224725"),
            ("buyer@example.com", "39053344705"),
            ("office@example.com", "11144477735"),
        ]:
            user = await create_user(session, UserCreate(**user_payload(email=email, cpf=cpf)))
            user.participation_status = ParticipationStatus.APPROVED
            user.is_admin = email == "admin@example.com"
            people.append(user)
        admin, driver, _, office_user = people
        from app.modules.garage.schemas import GarageVehicleCreate

        vehicle = Vehicle(
            **GarageVehicleCreate(**vehicle_payload()).model_dump(
                exclude={"relationship_type", "relationship_note"}
            )
        )
        session.add(vehicle)
        await session.flush()
        session.add(
            VehicleUser(
                user_id=driver.id,
                vehicle_id=vehicle.id,
                relationship_type=VehicleRelationshipType.OWNER,
                verification_status=VerificationStatus.VERIFIED,
                garage_status=GarageValidationStatus.ACTIVE,
            )
        )
        session.add(GarageMembership(user_id=driver.id, vehicle_id=vehicle.id))
        driver.free_garage_vehicle_id = vehicle.id
        office_data = WorkshopCreate(**workshop_payload()).model_dump()
        office_data["source"] = WorkshopSource.OWNER_CLAIMED
        workshop = Workshop(
            **office_data,
            verification_status=VerificationStatus.VERIFIED,
            submitted_by_user_id=office_user.id,
        )
        session.add(workshop)
        await session.flush()
        session.add(
            WorkshopUser(
                workshop_id=workshop.id,
                user_id=office_user.id,
                role=WorkshopUserRole.OWNER,
                verification_status=VerificationStatus.VERIFIED,
            )
        )
        await session.commit()
        record = await create_maintenance_record(
            session,
            vehicle.id,
            MaintenanceRecordCreate(**maintenance_payload(workshop_id=workshop.id)),
            driver,
        )
        storage.objects["verified/seed-invoice"] = b"%PDF-1.4\nsynthetic receipt\n%%EOF"
        session.add(
            Document(
                owner_user_id=driver.id,
                vehicle_id=vehicle.id,
                maintenance_record_id=record.id,
                maintenance_revision_id=record.current_revision_id,
                document_type=DocumentType.INVOICE,
                storage_key="verified/seed-invoice",
                file_name="invoice.pdf",
                original_file_name="invoice.pdf",
                content_type="application/pdf",
                storage_verified=True,
                review_status=DocumentReviewStatus.APPROVED,
                upload_status=DocumentUploadStatus.UPLOADED,
                processing_status=DocumentProcessingStatus.NOT_REQUESTED,
            )
        )
        await session.commit()
        await submit_maintenance(
            session, record.id, MaintenanceSubmit(revision_id=record.current_revision_id), driver
        )
        revision = await session.get(MaintenanceRevision, record.current_revision_id)
        await review_maintenance(
            session,
            record.id,
            MaintenanceReview(
                expected_version=revision.review_version,
                revision_id=revision.id,
                decision="approved",
                reason="Synthetic fixture inspected",
                public_description="Troca de óleo revisada",
            ),
            admin,
        )
    await dispose_engine()


asyncio.run(prepare())
app = create_app()
app.dependency_overrides[get_storage_client] = lambda: lambda: storage
app.dependency_overrides[garage_storage] = lambda: lambda: storage
app.dependency_overrides[get_payment_gateway] = lambda: gateway


@app.api_route("/__fixture-storage/{key:path}", methods=["GET", "PUT"])
async def fixture_storage(key: str, request: Request, access: str):
    if storage.urls.get(access) != key:
        raise HTTPException(404)
    if request.method == "PUT":
        storage.objects[key] = await request.body()
        return Response(status_code=200)
    if key not in storage.objects:
        raise HTTPException(404)
    return Response(storage.objects[key], media_type="application/pdf")


async def process_event(event_id):
    async with get_async_session_factory()() as session:
        await process_payment_event(session, event_id, gateway, datetime.now(UTC))


webhooks.dispatch_payment_event = lambda event_id: asyncio.create_task(process_event(event_id))
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8009, access_log=False)
