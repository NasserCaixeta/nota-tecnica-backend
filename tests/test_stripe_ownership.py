from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import select

from tests.test_payment_benefits import add_event, prepare_payment


async def test_stripe_owner_metadata_replaces_external_cpf_matching(client, db_session):
    from app.modules.payments.events import process_payment_event
    from app.modules.payments.models import HistoryAccessGrant

    order, gateway = await prepare_payment(client, db_session)
    gateway.payment = replace(gateway.payment, customer_user_reference=str(order.buyer_id))
    row = await add_event(db_session)
    row.provider = "stripe"
    await db_session.commit()
    await process_payment_event(db_session, row.id, gateway, datetime(2026, 10, 27, tzinfo=UTC))
    assert await db_session.scalar(select(HistoryAccessGrant)) is not None


async def test_legacy_payment_event_never_calls_stripe_or_grants_benefit(client, db_session):
    from app.modules.payments.events import process_payment_event
    from app.modules.payments.models import HistoryAccessGrant

    _, gateway = await prepare_payment(client, db_session)
    row = await add_event(db_session)
    row.provider = "asaas"
    await db_session.commit()
    await process_payment_event(db_session, row.id, gateway, datetime(2026, 10, 27, tzinfo=UTC))
    assert gateway.calls == []
    assert await db_session.scalar(select(HistoryAccessGrant)) is None
