from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.modules.users.models import User
from app.modules.vehicles.models import GarageValidationStatus, VehicleUser, VerificationStatus
from tests.test_maintenance import auth_headers, maintenance_payload
from tests.test_vehicles import vehicle_payload


async def add_subscription_period(session, buyer_id, start, end):
    from app.modules.payments.models import PaymentOrder, SubscriptionPeriod, VerifiedPayment

    order = PaymentOrder(
        id="subscription-order",
        buyer_id=buyer_id,
        product="garage_monthly",
        amount_cents=4900,
        currency="BRL",
        environment="sandbox",
        state="paid",
        provider_subscription_id="sub_1",
        callback_url="https://pilot.test",
        created_at=start,
    )
    session.add(order)
    await session.flush()
    payment = VerifiedPayment(
        order_id=order.id,
        provider_payment_id="pay_subscription",
        state="CONFIRMED",
        confirmed_at=start,
        checked_at=start,
    )
    session.add(payment)
    await session.flush()
    period = SubscriptionPeriod(
        order_id=order.id,
        payment_id=payment.id,
        buyer_id=buyer_id,
        provider_subscription_id="sub_1",
        starts_at=start,
        expires_at=end,
    )
    session.add(period)
    await session.commit()
    return period


async def prepare_six_vehicles(client, session):
    h = auth_headers(client)
    vehicles = []
    for i, plate in enumerate(("ABC1D23", "DEF2E34", "GHI3F45", "JKL4G56", "MNO5H67", "PQR6I78")):
        response = client.post(
            "/api/v1/garage/vehicles",
            headers=h,
            json=vehicle_payload(plate=plate, chassis=f"chassis-{i}", renavam=f"{10000000000 + i}"),
        )
        assert response.status_code == 201, response.text
        vehicles.append(response.json())
        link = await session.get(VehicleUser, response.json()["vehicle_link_id"])
        link.verification_status = VerificationStatus.VERIFIED
        link.garage_status = GarageValidationStatus.ACTIVE
    await session.commit()
    user = await session.scalar(select(User).where(User.email == "driver@example.com"))
    return h, user, vehicles


async def test_five_total_slots_and_expiry_preserve_reading(client, db_session):
    from app.modules.garage.policy import get_garage_capacity

    h, user, vehicles = await prepare_six_vehicles(client, db_session)
    start = datetime.now(UTC) - timedelta(days=1)
    end = start + timedelta(days=31)
    period = await add_subscription_period(db_session, user.id, start, end)
    capacity = await get_garage_capacity(db_session, user.id, end - timedelta(microseconds=1))
    assert capacity.limit == 5
    assert len(capacity.writable_vehicle_ids) == 5
    for index, vehicle in enumerate(vehicles):
        response = client.post(
            f"/api/v1/vehicles/{vehicle['vehicle_id']}/maintenance-records",
            headers=h,
            json=maintenance_payload(),
        )
        assert response.status_code == (201 if index < 5 else 403), response.text
    dashboard = client.get("/api/v1/garage", headers=h).json()
    assert [v["commercial_access"] for v in dashboard["vehicles"]] == ["free"] + [
        "subscription"
    ] * 4 + ["read_only"]
    capacity = await get_garage_capacity(db_session, user.id, end)
    assert capacity.limit == 1
    assert capacity.writable_vehicle_ids == {vehicles[0]["vehicle_id"]}
    period.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()
    second_id = vehicles[1]["vehicle_id"]
    assert (
        client.get(f"/api/v1/vehicles/{second_id}/maintenance-records", headers=h).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/vehicles/{second_id}/maintenance-records",
            headers=h,
            json=maintenance_payload(),
        ).status_code
        == 403
    )


async def test_free_vehicle_selection_requires_own_active_garage_link(client, db_session):
    h, _, vehicles = await prepare_six_vehicles(client, db_session)
    selected = vehicles[1]["vehicle_id"]
    response = client.patch("/api/v1/garage/free-vehicle", headers=h, json={"vehicle_id": selected})
    assert response.status_code == 200, response.text
    items = response.json()["vehicles"]
    assert next(v for v in items if v["vehicle_id"] == selected)["commercial_access"] == "free"
    assert (
        client.patch(
            "/api/v1/garage/free-vehicle", headers=h, json={"vehicle_id": 99999}
        ).status_code
        == 404
    )
    link = await db_session.get(VehicleUser, vehicles[2]["vehicle_link_id"])
    link.verification_status = VerificationStatus.REJECTED
    await db_session.commit()
    assert (
        client.patch(
            "/api/v1/garage/free-vehicle", headers=h, json={"vehicle_id": vehicles[2]["vehicle_id"]}
        ).status_code
        == 403
    )


async def test_cancellation_is_durable_and_preserves_confirmed_period(client, db_session):
    from app.modules.garage.policy import get_garage_capacity
    from app.modules.payments.models import SubscriptionCancellation
    from app.modules.payments.router import get_payment_gateway

    h, user, _ = await prepare_six_vehicles(client, db_session)
    now = datetime.now(UTC)
    period = await add_subscription_period(
        db_session, user.id, now - timedelta(days=1), now + timedelta(days=30)
    )

    class Gateway:
        calls = []

        async def cancel_subscription(self, subscription_id):
            row = await db_session.get(SubscriptionCancellation, "subscription-order")
            assert row is not None and row.status == "pending"
            self.calls.append(subscription_id)
            return True

    gateway = Gateway()
    client.app.dependency_overrides[get_payment_gateway] = lambda: gateway
    response = client.post("/api/v1/payments/subscriptions/subscription-order/cancel", headers=h)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "confirmed"
    assert (
        client.post(
            "/api/v1/payments/subscriptions/subscription-order/cancel", headers=h
        ).status_code
        == 200
    )
    assert gateway.calls == ["sub_1"]
    from app.modules.audit.models import AuditEvent

    decisions = list(
        await db_session.scalars(
            select(AuditEvent)
            .where(AuditEvent.action.like("payments.cancellation.%"))
            .order_by(AuditEvent.id)
        )
    )
    assert [event.action for event in decisions] == [
        "payments.cancellation.requested",
        "payments.cancellation.confirmed",
    ]
    assert [event.version for event in decisions] == [1, 2]
    assert decisions[0].actor_id == user.id
    assert decisions[1].actor_id is None
    assert all(event.event_metadata["order_id"] == "subscription-order" for event in decisions)

    assert period.revoked_at is None
    assert (await get_garage_capacity(db_session, user.id, now)).limit == 5
    other = auth_headers(client, email="other@example.com", cpf="39053344705")
    assert (
        client.post(
            "/api/v1/payments/subscriptions/subscription-order/cancel", headers=other
        ).status_code
        == 404
    )


async def test_subscription_does_not_grant_vehicle_relationship(client, db_session):
    import pytest
    from fastapi import HTTPException

    from app.modules.maintenance.schemas import MaintenanceRecordCreate
    from app.modules.maintenance.service import create_maintenance_record
    from app.modules.vehicles.models import Vehicle

    h = auth_headers(client)
    user = await db_session.scalar(select(User).where(User.email == "driver@example.com"))
    now = datetime.now(UTC)
    await add_subscription_period(
        db_session, user.id, now - timedelta(days=1), now + timedelta(days=30)
    )
    vehicle = Vehicle(plate="ABC1D23")
    db_session.add(vehicle)
    await db_session.commit()
    with pytest.raises(HTTPException) as exc:
        await create_maintenance_record(
            db_session, vehicle.id, MaintenanceRecordCreate(**maintenance_payload()), user
        )
    assert exc.value.status_code == 404
    assert client.get("/api/v1/history/vehicles/ABC1D23", headers=h).status_code == 403


async def test_free_vehicle_falls_back_to_first_valid_relationship(client, db_session):
    from app.modules.garage.policy import get_garage_capacity

    _, user, vehicles = await prepare_six_vehicles(client, db_session)
    first = await db_session.get(VehicleUser, vehicles[0]["vehicle_link_id"])
    first.verification_status = VerificationStatus.REJECTED
    first.garage_status = GarageValidationStatus.REJECTED
    await db_session.commit()
    capacity = await get_garage_capacity(db_session, user.id, datetime.now(UTC))
    assert capacity.free_vehicle_id == vehicles[1]["vehicle_id"]


async def test_failed_cancellation_is_recoverable_without_losing_paid_period(client, db_session):
    from app.modules.payments.cancellations import reconcile_cancellation
    from app.modules.payments.gateway import GatewayUncertainOutcome
    from app.modules.payments.models import SubscriptionCancellation
    from app.modules.payments.router import get_payment_gateway

    h, user, _ = await prepare_six_vehicles(client, db_session)
    now = datetime.now(UTC)
    period = await add_subscription_period(
        db_session, user.id, now - timedelta(days=1), now + timedelta(days=30)
    )

    class Gateway:
        failed = True

        async def cancel_subscription(self, subscription_id):
            if self.failed:
                raise GatewayUncertainOutcome()
            return True

    gateway = Gateway()
    client.app.dependency_overrides[get_payment_gateway] = lambda: gateway
    response = client.post("/api/v1/payments/subscriptions/subscription-order/cancel", headers=h)
    assert response.status_code == 200
    assert response.json()["status"] == "reconciliation_required"
    assert (
        await db_session.get(SubscriptionCancellation, "subscription-order")
    ).confirmed_at is None
    gateway.failed = False
    await reconcile_cancellation(db_session, "subscription-order", gateway)
    assert (
        await db_session.get(SubscriptionCancellation, "subscription-order")
    ).status == "confirmed"
    assert period.revoked_at is None


async def test_additional_vehicle_can_acknowledge_and_dispute_without_subscription(
    client, db_session
):
    from app.modules.maintenance.models import MaintenanceRevision
    from tests.test_maintenance_moderation import approve_workshop_for_test

    customer, user, vehicles = await prepare_six_vehicles(client, db_session)
    office = auth_headers(client, email="office@example.com", cpf="39053344705")
    workshop_id = approve_workshop_for_test(client, office)
    from app.modules.workshops.models import WorkshopUser

    responsibility = await db_session.scalar(
        select(WorkshopUser).where(WorkshopUser.workshop_id == workshop_id)
    )
    office_user = await db_session.scalar(select(User).where(User.email == "office@example.com"))
    responsibility.user_id = office_user.id
    await db_session.commit()
    response = client.post(
        f"/api/v1/workshops/{workshop_id}/maintenance-records",
        headers=office,
        json={**maintenance_payload(), "plate": vehicles[1]["plate"]},
    )
    assert response.status_code == 201
    record = response.json()
    revision = await db_session.get(MaintenanceRevision, record["current_revision_id"])
    revision.customer_user_id = user.id
    await db_session.commit()
    assert (
        client.post(
            f"/api/v1/maintenance-records/{record['id']}/acknowledge",
            headers=customer,
            json={"revision_id": revision.id},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/maintenance-records/{record['id']}/disputes",
            headers=customer,
            json={
                "revision_id": revision.id,
                "reason": "Peça instalada não corresponde ao serviço",
            },
        ).status_code
        == 201
    )


async def test_refund_revokes_period_after_remote_subscription_deletion(client, db_session):
    from app.modules.payments.events import process_payment_event
    from app.modules.payments.gateway import ProviderPayment
    from tests.test_payment_benefits import FinancialGateway, add_event

    auth_headers(client)
    user = await db_session.scalar(select(User).where(User.email == "driver@example.com"))
    now = datetime.now(UTC)
    period = await add_subscription_period(
        db_session, user.id, now - timedelta(days=1), now + timedelta(days=30)
    )
    # A known receipt must be revocable even when auxiliary remote resources disappeared.
    gateway = FinancialGateway(
        ProviderPayment(
            id="pay_subscription",
            state="REFUNDED",
            order_reference="subscription-order",
            amount_cents=4900,
            currency="BRL",
            customer_id="deleted-customer",
            subscription_id="sub_1",
        )
    )
    event = await add_event(db_session, payment_id="pay_subscription", kind="PAYMENT_REFUNDED")
    await process_payment_event(db_session, event.id, gateway, now)
    assert period.revoked_at is not None
    assert event.status == "processed"
