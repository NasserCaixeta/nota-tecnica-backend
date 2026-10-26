from app.modules.vehicles.models import GarageValidationStatus, VehicleUser, VerificationStatus
from tests.test_maintenance import auth_headers, maintenance_payload
from tests.test_vehicles import vehicle_payload


def test_old_vehicle_route_cannot_bypass_free_vehicle_limit(client):
    headers = auth_headers(client)
    first = client.post("/api/v1/vehicles", headers=headers, json=vehicle_payload())
    assert first.status_code == 201
    second = client.post(
        "/api/v1/vehicles",
        headers=headers,
        json=vehicle_payload(plate="DEF2E34", chassis="other-chassis", renavam="98765432100"),
    )
    assert second.status_code == 201
    record = client.post(
        f"/api/v1/vehicles/{second.json()['id']}/maintenance-records",
        headers=headers,
        json=maintenance_payload(),
    )
    assert record.status_code == 403


def test_declaring_existing_plate_does_not_reveal_previous_history(client):
    owner = auth_headers(client)
    created = client.post("/api/v1/garage/vehicles", headers=owner, json=vehicle_payload())
    vehicle_id = created.json()["vehicle_id"]
    record = client.post(
        f"/api/v1/vehicles/{vehicle_id}/maintenance-records",
        headers=owner,
        json=maintenance_payload(),
    )
    assert record.status_code == 201
    stranger = auth_headers(client, email="other@example.com", cpf="39053344705")
    linked = client.post("/api/v1/garage/vehicles", headers=stranger, json=vehicle_payload())
    assert linked.status_code == 201
    history = client.get(f"/api/v1/vehicles/{vehicle_id}/maintenance-records", headers=stranger)
    assert history.status_code == 200
    assert history.json() == []
    detail = client.get(f"/api/v1/maintenance-records/{record.json()['id']}", headers=stranger)
    assert detail.status_code == 403


async def test_validated_additional_vehicle_remains_readable_without_subscription(
    client, db_session
):
    headers = auth_headers(client)
    client.post("/api/v1/garage/vehicles", headers=headers, json=vehicle_payload())
    second = client.post(
        "/api/v1/garage/vehicles",
        headers=headers,
        json=vehicle_payload(plate="DEF2E34", chassis="another-chassis", renavam="98765432100"),
    )
    link = await db_session.get(VehicleUser, second.json()["vehicle_link_id"])
    link.verification_status = VerificationStatus.VERIFIED
    link.garage_status = GarageValidationStatus.ACTIVE
    await db_session.commit()
    vehicle_id = second.json()["vehicle_id"]
    assert (
        client.get(
            f"/api/v1/vehicles/{vehicle_id}/maintenance-records", headers=headers
        ).status_code
        == 200
    )
    blocked = client.post(
        f"/api/v1/vehicles/{vehicle_id}/maintenance-records",
        headers=headers,
        json=maintenance_payload(),
    )
    assert blocked.status_code == 403


def test_conflicting_vehicle_identifiers_do_not_reveal_or_overwrite_original(client):
    owner = auth_headers(client)
    client.post("/api/v1/garage/vehicles", headers=owner, json=vehicle_payload())
    other = auth_headers(client, email="other@example.com", cpf="39053344705")
    conflicting = client.post(
        "/api/v1/garage/vehicles", headers=other, json=vehicle_payload(chassis="wrong-chassis")
    )
    assert conflicting.status_code == 409
    assert "9BWZZZ377VT004251" not in conflicting.text
