from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.modules.users.models import User
from tests.test_maintenance import auth_headers
from tests.test_maintenance_moderation import approve_customer_service


async def add_history_grant(
    session, buyer_id, vehicle_id, *, starts_at=None, order_id="history-order"
):
    from app.modules.payments.models import HistoryAccessGrant, PaymentOrder, VerifiedPayment

    starts_at = starts_at or datetime.now(UTC) - timedelta(hours=1)
    session.add(
        PaymentOrder(
            id=order_id,
            buyer_id=buyer_id,
            product="history_access",
            vehicle_id=vehicle_id,
            amount_cents=1900,
            currency="BRL",
            environment="sandbox",
            state="paid",
            callback_url="https://pilot.test",
            created_at=starts_at,
        )
    )
    await session.flush()
    payment = VerifiedPayment(
        order_id=order_id,
        provider_payment_id=f"pay-{order_id}",
        state="CONFIRMED",
        confirmed_at=starts_at,
        checked_at=starts_at,
    )
    session.add(payment)
    await session.flush()
    grant = HistoryAccessGrant(
        order_id=order_id,
        payment_id=payment.id,
        buyer_id=buyer_id,
        vehicle_id=vehicle_id,
        starts_at=starts_at,
        expires_at=starts_at + timedelta(hours=720),
    )
    session.add(grant)
    await session.commit()
    return grant


async def test_paid_history_exact_expiry_and_identity_boundaries(client, db_session):
    from app.modules.payments.access import has_history_access
    from tests.test_payment_benefits import prepare_payment

    order, _ = await prepare_payment(client, db_session)
    start = datetime(2026, 10, 1, 12, tzinfo=UTC)
    grant = await add_history_grant(db_session, order.buyer_id, order.vehicle_id, starts_at=start)
    expiry = start + timedelta(hours=720)
    assert await has_history_access(
        db_session, order.buyer_id, order.vehicle_id, expiry - timedelta(microseconds=1)
    )
    assert not await has_history_access(db_session, order.buyer_id, order.vehicle_id, expiry)
    assert not await has_history_access(
        db_session, order.buyer_id, order.vehicle_id, expiry + timedelta(microseconds=1)
    )
    assert not await has_history_access(db_session, order.buyer_id + 1, order.vehicle_id, start)
    assert not await has_history_access(db_session, order.buyer_id, order.vehicle_id + 1, start)
    grant.revoked_at = start
    await db_session.commit()
    assert not await has_history_access(db_session, order.buyer_id, order.vehicle_id, start)


async def test_bought_history_is_sanitized_and_rechecks_publication(client, db_session):
    owner, vehicle_id, record, _, admin, _ = await approve_customer_service(client, db_session)
    buyer_headers = auth_headers(client, email="buyer@example.com", cpf="39053344705")
    buyer = await db_session.scalar(select(User).where(User.email == "buyer@example.com"))
    url = "/api/v1/history/vehicles/ABC1D23"
    assert client.get(url, headers=buyer_headers).status_code == 403
    await add_history_grant(db_session, buyer.id, vehicle_id)
    result = client.get(url, headers=buyer_headers)
    assert result.status_code == 200, result.text
    assert result.json()["access"]["source"] == "purchase"
    assert result.json()["records"][0]["public_description"] == "Troca de óleo e filtros"
    for forbidden in (
        "cpf",
        "renavam",
        "storage_key",
        "owner_user_id",
        "author_user_id",
        "review_reason",
        "document",
    ):
        assert forbidden not in result.text
    assert client.get(url, headers=owner).json()["access"]["source"] == "relationship"
    # New relevant edits immediately remove ineligible history during a valid purchase.
    from tests.test_maintenance import maintenance_payload

    edited = client.patch(
        f"/api/v1/maintenance-records/{record['id']}",
        headers=owner,
        json=maintenance_payload(description="Correção aguardando nova moderação"),
    )
    assert edited.status_code == 200
    assert client.get(url, headers=buyer_headers).json()["records"] == []
    # The purchase is live: a newly approved service appears in the same period.
    from tests.test_documents import create_uploaded_document
    from tests.test_maintenance_moderation import create_record, submit

    new_record = create_record(client, owner, vehicle_id, description="Novo serviço")
    proof = create_uploaded_document(
        client, vehicle_id, owner, maintenance_record_id=new_record["id"], document_type="invoice"
    )
    assert (
        client.patch(
            f"/api/v1/admin/documents/{proof['id']}/review",
            headers=admin,
            json={"expected_version": 1, "review_status": "approved"},
        ).status_code
        == 200
    )
    submitted = submit(client, new_record, owner)
    assert submitted.status_code == 200
    assert (
        client.patch(
            f"/api/v1/admin/maintenance-reviews/{new_record['id']}",
            headers=admin,
            json={
                "expected_version": submitted.json()["review_version"],
                "revision_id": submitted.json()["current_revision_id"],
                "decision": "approved",
                "reason": "Comprovante inspecionado",
                "public_description": "Novo serviço revisado",
            },
        ).status_code
        == 200
    )
    assert (
        client.get(url, headers=buyer_headers).json()["records"][0]["public_description"]
        == "Novo serviço revisado"
    )

    assert client.get("/api/v1/history/vehicles/DEF2E34", headers=buyer_headers).status_code == 403
