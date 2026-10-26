from tests.test_maintenance import auth_headers, create_vehicle, maintenance_payload
from tests.test_maintenance_moderation import approve_customer_service


def test_private_vehicle_and_unknown_plate_have_indistinguishable_previews(client):
    h = auth_headers(client)
    v = create_vehicle(client, h)
    client.post(f"/api/v1/vehicles/{v}/maintenance-records", headers=h, json=maintenance_payload())
    known = client.get("/api/v1/public/vehicles/ABC1D23/history-preview").json()
    unknown = client.get("/api/v1/public/vehicles/XYZ9A87/history-preview").json()
    known.pop("plate")
    unknown.pop("plate")
    assert known == unknown
    assert known["vehicle_found"] is False


async def test_purchased_projection_uses_reviewed_description_and_only_explicit_fields(
    client, db_session
):
    from app.modules.maintenance.models import MaintenanceRecord, MaintenanceRevision
    from app.modules.maintenance.projections import build_published_maintenance_read

    _, _, data, _, _, _ = await approve_customer_service(client, db_session)
    record = await db_session.get(MaintenanceRecord, data["id"])
    record.description = "CPF 52998224725, Rua privada 123"
    revision = await db_session.get(MaintenanceRevision, record.current_revision_id)
    payload = build_published_maintenance_read(record, revision, None).model_dump(mode="json")
    private_fields = {
        "author_user_id",
        "customer_user_id",
        "documents",
        "vehicle_id",
        "chassis",
        "renavam",
        "snapshot",
        "description",
        "cpf",
        "address",
        "review_reason",
    }
    assert private_fields.isdisjoint(payload)
    assert payload["public_description"] == "Troca de óleo e filtros"
    assert "52998224725" not in str(payload)
    assert payload["labor_cost"] == "120.00"
    assert payload["parts_cost"] == "180.00"
    assert payload["total_cost"] == "300.00"


async def test_dispute_immediately_removes_public_dates_and_count(client, db_session):
    h, _, record, _, _, _ = await approve_customer_service(client, db_session)
    before = client.get("/api/v1/public/vehicles/ABC1D23/history-preview").json()
    assert before["first_maintenance_date"] == "2026-06-15"
    r = client.post(
        f"/api/v1/maintenance-records/{record['id']}/disputes",
        headers=h,
        json={"revision_id": record["current_revision_id"], "reason": "Invoice does not match"},
    )
    assert r.status_code == 201
    after = client.get("/api/v1/public/vehicles/ABC1D23/history-preview").json()
    assert after["maintenance_count"] == 0
    assert after["vehicle_found"] is False
    assert after["first_maintenance_date"] is None
    assert after["last_maintenance_date"] is None
