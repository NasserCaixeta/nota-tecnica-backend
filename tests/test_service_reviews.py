import pytest

from tests.test_maintenance import auth_headers
from tests.test_maintenance_moderation import approve_customer_service, approve_workshop_for_test


@pytest.mark.parametrize("stars", [0, 6])
async def test_review_rejects_invalid_stars(client, db_session, stars):
    h, _, record, _, _, _ = await approve_customer_service(client, db_session)
    r = client.put(
        f"/api/v1/maintenance-records/{record['id']}/review",
        headers=h,
        json={"revision_id": record["current_revision_id"], "stars": stars},
    )
    assert r.status_code == 422


async def test_customer_can_review_only_current_published_service(client, db_session):
    h, _, record, _, _, _ = await approve_customer_service(client, db_session)
    payload = {"revision_id": record["current_revision_id"], "stars": 4, "comment": "Good service"}
    r = client.put(f"/api/v1/maintenance-records/{record['id']}/review", headers=h, json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["stars"] == 4
    changed = client.patch(
        f"/api/v1/maintenance-records/{record['id']}",
        headers=h,
        json={
            "description": "Corrected version",
            "expected_revision_id": record["current_revision_id"],
        },
    )
    assert changed.status_code == 200
    stale = client.put(
        f"/api/v1/maintenance-records/{record['id']}/review", headers=h, json=payload
    )
    assert stale.status_code == 409


async def test_workshop_responsible_cannot_review_own_workshop(client, db_session):
    h = auth_headers(client)
    office = approve_workshop_for_test(client, h)
    _, _, record, _, _, _ = await approve_customer_service(
        client, db_session, workshop_id=office, headers=h
    )
    r = client.put(
        f"/api/v1/maintenance-records/{record['id']}/review",
        headers=h,
        json={"revision_id": record["current_revision_id"], "stars": 5},
    )
    assert r.status_code == 403


async def test_service_detail_exposes_rating_permission_and_author_can_resume_own_review(
    client, db_session
):
    h, _, record, _, _, _ = await approve_customer_service(client, db_session)
    assert (
        client.get(f"/api/v1/maintenance-records/{record['id']}", headers=h).json()["permissions"][
            "can_review"
        ]
        is True
    )
    saved = client.put(
        f"/api/v1/maintenance-records/{record['id']}/review",
        headers=h,
        json={"revision_id": record["current_revision_id"], "stars": 4, "comment": "Good"},
    ).json()
    own = client.get(f"/api/v1/maintenance-records/{record['id']}/review", headers=h)
    assert own.status_code == 200
    assert own.json()["id"] == saved["id"]


async def test_admin_can_moderate_comment_without_changing_customer_stars(client, db_session):
    h, _, record, _, admin, _ = await approve_customer_service(client, db_session)
    saved = client.put(
        f"/api/v1/maintenance-records/{record['id']}/review",
        headers=h,
        json={"revision_id": record["current_revision_id"], "stars": 4, "comment": "Comment"},
    ).json()
    url = f"/api/v1/admin/service-reviews/{saved['id']}"
    assert (
        client.patch(
            url,
            headers=admin,
            json={
                "expected_version": 1,
                "comment_hidden": True,
                "reason": "Privacy review",
                "stars": 5,
            },
        ).status_code
        == 422
    )
    response = client.patch(
        url,
        headers=admin,
        json={"expected_version": 1, "comment_hidden": True, "reason": "Privacy review"},
    )
    assert response.status_code == 200
    assert response.json()["stars"] == 4
    assert response.json()["comment_hidden"] is True


@pytest.mark.parametrize("comment", ["Private contact", "Reworded private contact"])
async def test_editing_review_does_not_undo_comment_moderation(client, db_session, comment):
    from app.modules.ranking.models import ServiceReview

    h, _, record, _, admin, _ = await approve_customer_service(client, db_session)
    url = f"/api/v1/maintenance-records/{record['id']}/review"
    saved = client.put(
        url,
        headers=h,
        json={
            "revision_id": record["current_revision_id"],
            "stars": 4,
            "comment": "Private contact",
        },
    ).json()
    hidden = client.patch(
        f"/api/v1/admin/service-reviews/{saved['id']}",
        headers=admin,
        json={"expected_version": 1, "comment_hidden": True, "reason": "Personal data"},
    )
    assert hidden.status_code == 200
    edited = client.put(
        url,
        headers=h,
        json={
            "revision_id": record["current_revision_id"],
            "expected_version": 2,
            "stars": 3,
            "comment": comment,
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["stars"] == 3
    assert edited.json()["comment_hidden"] is True
    review = await db_session.get(ServiceReview, saved["id"])
    assert review.moderation_reason == "Personal data"
