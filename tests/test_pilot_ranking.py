from decimal import Decimal

import pytest


@pytest.mark.parametrize(
    "values,score,eligible,label",
    [
        ((10, Decimal("4"), 10, 8), Decimal("7.4"), True, "sufficient"),
        ((10, None, 10, 8), Decimal("7"), True, "sufficient"),
        ((0, None, 0, 0), None, False, "no_data"),
        ((4, Decimal("5"), 0, 0), Decimal("7.333333333333333333333333333"), False, "small_sample"),
        ((5, None, 0, 0), None, False, "insufficient_quality_data"),
    ],
)
def test_pilot_score_uses_only_measured_components(values, score, eligible, label):
    from app.modules.ranking.scoring import PilotScoreInput, calculate_pilot_score

    result = calculate_pilot_score(PilotScoreInput(*values))
    assert result.score == score
    assert result.eligible_for_ranking is eligible
    assert result.sample_label == label


async def seed_public_services(client, db_session, count, *, verified=True, stars=4):
    from app.modules.documents.models import Document, DocumentReviewStatus
    from app.modules.maintenance.models import MaintenanceRevision
    from app.modules.ranking.models import ServiceReview
    from app.modules.vehicles.models import VerificationStatus
    from app.modules.workshops.models import Workshop
    from tests.test_documents import create_uploaded_document
    from tests.test_maintenance import auth_headers, create_vehicle
    from tests.test_maintenance_moderation import activate_link, create_record
    from tests.test_workshop_claims import create_reference

    h = auth_headers(client)
    v = create_vehicle(client, h)
    activate_link(client, v)
    office = create_reference(client, h)
    workshop = await db_session.get(Workshop, office["id"])
    if verified:
        workshop.verification_status = VerificationStatus.VERIFIED
        await db_session.commit()
    records = []
    for index in range(count):
        record = create_record(
            client,
            h,
            v,
            workshop_id=office["id"],
            actual_delivery_date="2026-06-15" if index < 8 else "2026-06-16",
        )
        proof = create_uploaded_document(
            client, v, h, maintenance_record_id=record["id"], document_type="invoice"
        )
        revision = await db_session.get(MaintenanceRevision, record["current_revision_id"])
        revision.admin_status = "approved"
        revision.editorial_status = "submitted"
        revision.public_description = "Serviço conferido"
        document = await db_session.get(Document, proof["id"])
        document.review_status = DocumentReviewStatus.APPROVED
        if stars:
            db_session.add(
                ServiceReview(
                    record_id=record["id"],
                    revision_id=revision.id,
                    customer_user_id=record["author_user_id"],
                    stars=stars,
                )
            )
        await db_session.commit()
        records.append(record)
    return h, office["id"], records


async def test_ranking_uses_current_public_revisions_and_recalculates_after_dispute(
    client, db_session
):
    h, office, records = await seed_public_services(client, db_session, 10)
    ranked = client.get("/api/v1/public/workshops/ranking").json()
    assert ranked["score_version"] == "pilot_v1"
    item = ranked["items"][0]
    assert item["workshop_id"] == office
    assert item["score"] == "7.4"
    assert item["review_count"] == item["measured_deadline_count"] == 10
    assert item["completed_services_count"] == 10
    record = records[0]
    assert (
        client.post(
            f"/api/v1/maintenance-records/{record['id']}/disputes",
            headers=h,
            json={"revision_id": record["current_revision_id"], "reason": "New dispute"},
        ).status_code
        == 201
    )
    after = client.get("/api/v1/public/workshops/ranking").json()["items"][0]
    assert after["completed_services_count"] == after["review_count"] == 9
    assert after["measured_deadline_count"] == 9
    assert client.get("/api/v1/public/workshops/ranking?category=electrical").json()["items"] == []


async def test_small_sample_is_not_in_main_ranking_and_unverified_office_is_excluded(
    client, db_session
):
    _, office, _ = await seed_public_services(client, db_session, 4)
    data = client.get("/api/v1/public/workshops/ranking").json()
    assert data["items"] == []
    assert data["unranked_items"][0]["workshop_id"] == office
    assert data["unranked_items"][0]["sample_label"] == "small_sample"
    from app.modules.vehicles.models import VerificationStatus
    from app.modules.workshops.models import Workshop

    workshop = await db_session.get(Workshop, office)
    workshop.verification_status = VerificationStatus.PENDING
    await db_session.commit()
    data = client.get("/api/v1/public/workshops/ranking").json()
    assert data["items"] == data["unranked_items"] == []


async def test_review_stops_contributing_when_customer_becomes_workshop_representative(
    client, db_session
):
    from app.modules.vehicles.models import VerificationStatus
    from app.modules.workshops.models import WorkshopUser, WorkshopUserRole

    _, office, records = await seed_public_services(client, db_session, 5)
    assert client.get("/api/v1/public/workshops/ranking").json()["items"][0]["review_count"] == 5
    db_session.add(
        WorkshopUser(
            workshop_id=office,
            user_id=records[0]["author_user_id"],
            role=WorkshopUserRole.OWNER,
            verification_status=VerificationStatus.VERIFIED,
        )
    )
    await db_session.commit()
    assert client.get("/api/v1/public/workshops/ranking").json()["items"][0]["review_count"] == 0


async def test_public_performance_has_no_personal_reviewer_data(client, db_session):
    _, office, _ = await seed_public_services(client, db_session, 5)
    r = client.get(f"/api/v1/public/workshops/{office}/performance")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["metrics"]["review_count"] == 5
    assert all(
        {"customer_user_id", "full_name", "email", "vehicle_id", "plate"}.isdisjoint(review)
        for review in data["reviews"]
    )
    from sqlalchemy import select

    from app.modules.maintenance.models import MaintenanceRevision

    revision = await db_session.scalar(select(MaintenanceRevision).limit(1))
    revision.admin_status = "pending"
    await db_session.commit()
    assert (
        client.get(f"/api/v1/public/workshops/{office}/performance").json()["metrics"][
            "review_count"
        ]
        == 4
    )
