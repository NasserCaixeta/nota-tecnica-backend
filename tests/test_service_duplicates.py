from tests.test_maintenance import auth_headers, create_vehicle
from tests.test_maintenance_moderation import create_record
from tests.test_participation_admin import admin_headers


async def test_duplicate_association_requires_admin_versions_and_preserves_authors(
    client, db_session
):
    h = auth_headers(client)
    v = create_vehicle(client, h)
    first = create_record(client, h, v)
    second = create_record(client, h, v)
    assert first["id"] != second["id"]
    payload = {
        "other_record_id": second["id"],
        "revision_id": first["current_revision_id"],
        "other_revision_id": second["current_revision_id"],
        "reason": "Same receipt, verified",
    }
    suggested = client.post(
        f"/api/v1/maintenance-records/{first['id']}/associate", headers=h, json=payload
    )
    assert suggested.status_code == 202, suggested.text
    # A suggestion alone cannot collapse records.
    assert (
        client.get(f"/api/v1/maintenance-records/{second['id']}", headers=h).json()[
            "superseded_by_id"
        ]
        is None
    )
    admin = await admin_headers(client, db_session)
    resolved = client.post(
        f"/api/v1/maintenance-records/{first['id']}/associate", headers=admin, json=payload
    )
    assert resolved.status_code == 200, resolved.text
    canonical = resolved.json()
    assert canonical["current_revision_id"] != first["current_revision_id"]
    assert canonical["admin_status"] == "pending"
    secondary = client.get(f"/api/v1/maintenance-records/{second['id']}", headers=h).json()
    assert secondary["superseded_by_id"] == first["id"]
    assert secondary["author_user_id"] == first["author_user_id"]
    assert secondary["published"] is False
    assert (
        client.post(
            f"/api/v1/maintenance-records/{first['id']}/associate", headers=admin, json=payload
        ).status_code
        == 409
    )


async def test_two_origins_consolidate_into_one_public_identity(client, db_session):
    from app.modules.maintenance.models import MaintenanceRevision
    from tests.test_documents import create_uploaded_document
    from tests.test_maintenance import maintenance_payload
    from tests.test_maintenance_moderation import (
        approve_customer_service,
        approve_workshop_for_test,
        submit,
    )

    h = auth_headers(client)
    office = approve_workshop_for_test(client, h)
    h, v, first, _, admin, _ = await approve_customer_service(
        client, db_session, workshop_id=office, headers=h
    )
    second_response = client.post(
        f"/api/v1/workshops/{office}/maintenance-records",
        headers=h,
        json={**maintenance_payload(), "plate": "ABC1D23"},
    )
    assert second_response.status_code == 201
    second = second_response.json()

    # Recognition is independently exercised through invitations in its own route tests.
    async def recognize():
        s = client.app.state.test_db_session
        revision = await s.get(MaintenanceRevision, second["current_revision_id"])
        revision.customer_user_id = first["author_user_id"]
        revision.customer_acknowledgement = "confirmed"
        await s.commit()

    client.portal.call(recognize)

    async def approve(record):
        doc = create_uploaded_document(
            client, v, h, maintenance_record_id=record["id"], document_type="invoice"
        )
        submitted = submit(client, record, h)
        assert submitted.status_code == 200, submitted.text
        assert (
            client.patch(
                f"/api/v1/admin/documents/{doc['id']}/review",
                headers=admin,
                json={"expected_version": 1, "review_status": "approved"},
            ).status_code
            == 200
        )
        current = client.get(
            f"/api/v1/admin/maintenance-reviews/{record['id']}", headers=admin
        ).json()
        result = client.patch(
            f"/api/v1/admin/maintenance-reviews/{record['id']}",
            headers=admin,
            json={
                "expected_version": current["review_version"],
                "revision_id": current["current_revision_id"],
                "decision": "approved",
                "reason": "Inspected",
                "public_description": "Troca de óleo",
            },
        )
        assert result.status_code == 200, result.text

    await approve(second)
    assert (
        client.get("/api/v1/public/vehicles/ABC1D23/history-preview").json()["maintenance_count"]
        == 2
    )
    resolved = client.post(
        f"/api/v1/maintenance-records/{first['id']}/associate",
        headers=admin,
        json={
            "other_record_id": second["id"],
            "revision_id": first["current_revision_id"],
            "other_revision_id": second["current_revision_id"],
            "reason": "Same receipt confirmed",
        },
    )
    assert resolved.status_code == 200, resolved.text
    consolidated = resolved.json()
    assert (
        client.get("/api/v1/public/vehicles/ABC1D23/history-preview").json()["maintenance_count"]
        == 0
    )
    confirmation = client.post(
        f"/api/v1/maintenance-records/{first['id']}/acknowledge",
        headers=h,
        json={"revision_id": consolidated["current_revision_id"]},
    )
    assert confirmation.status_code == 200
    await approve(consolidated)
    assert (
        client.get("/api/v1/public/vehicles/ABC1D23/history-preview").json()["maintenance_count"]
        == 1
    )
