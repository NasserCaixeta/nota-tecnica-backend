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
