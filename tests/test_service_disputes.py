import pytest

from tests.test_documents import FakeStorageClient
from tests.test_maintenance_moderation import approve_customer_service


async def test_dispute_after_confirmation_immediately_withdraws_publication(client, db_session):
    h, v, record, _, admin, _ = await approve_customer_service(client, db_session)
    response = client.post(
        f"/api/v1/maintenance-records/{record['id']}/disputes",
        headers=h,
        json={
            "revision_id": record["current_revision_id"],
            "reason": "Receipt lists a different part",
        },
    )
    assert response.status_code == 201, response.text
    dispute = response.json()
    detail = client.get(f"/api/v1/maintenance-records/{record['id']}", headers=h).json()
    assert detail["published"] is False
    assert detail["customer_acknowledgement"] == "disputed"
    assert (
        client.get("/api/v1/public/vehicles/ABC1D23/history-preview").json()["maintenance_count"]
        == 0
    )
    assert len(client.get("/api/v1/admin/service-disputes", headers=admin).json()) == 1
    resolved = client.patch(
        f"/api/v1/admin/service-disputes/{dispute['id']}",
        headers=admin,
        json={
            "expected_version": dispute["review_version"],
            "resolution": "resolved",
            "reason": "Customer still refuses the original version",
        },
    )
    assert resolved.status_code == 200, resolved.text
    detail = client.get(f"/api/v1/maintenance-records/{record['id']}", headers=h).json()
    assert detail["customer_acknowledgement"] == "disputed"
    assert detail["published"] is False
    stale = client.patch(
        f"/api/v1/admin/service-disputes/{dispute['id']}",
        headers=admin,
        json={
            "expected_version": dispute["review_version"],
            "resolution": "resolved",
            "reason": "Again",
        },
    )
    assert stale.status_code == 409
    repeated = client.post(
        f"/api/v1/maintenance-records/{record['id']}/disputes",
        headers=h,
        json={
            "revision_id": record["current_revision_id"],
            "reason": "Receipt lists a different part",
        },
    )
    assert repeated.status_code == 409
    reopened = client.post(
        f"/api/v1/maintenance-records/{record['id']}/disputes",
        headers=h,
        json={
            "revision_id": record["current_revision_id"],
            "reason": "New evidence: invoice cancelled",
        },
    )
    assert reopened.status_code == 201


async def test_dispute_evidence_is_private_and_does_not_become_service_receipt(client, db_session):
    from app.modules.documents.router import get_storage_client
    from tests.test_maintenance import auth_headers

    h, _, record, _, _, _ = await approve_customer_service(client, db_session)
    dispute = client.post(
        f"/api/v1/maintenance-records/{record['id']}/disputes",
        headers=h,
        json={"revision_id": record["current_revision_id"], "reason": "Wrong receipt"},
    ).json()
    client.app.dependency_overrides[get_storage_client] = lambda: lambda: FakeStorageClient()
    proof = client.post(
        f"/api/v1/service-disputes/{dispute['id']}/documents/upload-intents",
        headers=h,
        json={
            "document_type": "invoice",
            "file_name": "private.pdf",
            "content_type": "application/pdf",
        },
    )
    assert proof.status_code == 201, proof.text
    document = proof.json()["document"]
    assert document["service_dispute_id"] == dispute["id"]
    assert document["maintenance_revision_id"] is None
    other = auth_headers(client, email="other@example.com", cpf="39053344705")
    assert client.get(f"/api/v1/documents/{document['id']}", headers=other).status_code == 404


@pytest.mark.parametrize(
    "updates",
    [
        {"labor_cost": "130.00"},
        {"service_date": "2026-06-16"},
        {"description": "Corrected description"},
    ],
)
async def test_relevant_correction_preserves_previous_snapshot_and_requires_new_analysis(
    client,
    db_session,
    updates,
):
    h, _, record, _, _, _ = await approve_customer_service(client, db_session)
    changed = client.patch(
        f"/api/v1/maintenance-records/{record['id']}",
        headers=h,
        json={**updates, "expected_revision_id": record["current_revision_id"]},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["admin_status"] == "pending"
    assert changed.json()["published"] is False
    history = client.get(f"/api/v1/maintenance-records/{record['id']}/revisions", headers=h)
    assert history.status_code == 200, history.text
    assert len(history.json()) == 2
    assert history.json()[0]["snapshot"]["labor_cost"] == "120.00"
    assert history.json()[0]["snapshot"]["description"] == "Oil and filter change"
    assert history.json()[0]["admin_status"] == "approved"
    stale = client.patch(
        f"/api/v1/maintenance-records/{record['id']}",
        headers=h,
        json={"labor_cost": "500.00", "expected_revision_id": record["current_revision_id"]},
    )
    assert stale.status_code == 409
