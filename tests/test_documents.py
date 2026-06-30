from fastapi.testclient import TestClient

from tests.test_maintenance import auth_headers, create_vehicle, maintenance_payload


def document_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "document_type": "crlv",
        "file_name": "crlv.pdf",
        "content_type": "application/pdf",
        "storage_key": "vehicles/ABC1D23/crlv.pdf",
    }
    payload.update(overrides)
    return payload


def test_linked_user_can_create_vehicle_document(client: TestClient) -> None:
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)

    response = client.post(
        f"/api/v1/vehicles/{vehicle_id}/documents",
        json=document_payload(),
        headers=headers,
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["vehicle_id"] == vehicle_id
    assert data["document_type"] == "crlv"
    assert data["review_status"] == "pending"


def test_document_can_reference_same_vehicle_maintenance(client: TestClient) -> None:
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    record = client.post(
        f"/api/v1/vehicles/{vehicle_id}/maintenance-records",
        json=maintenance_payload(),
        headers=headers,
    )

    response = client.post(
        f"/api/v1/vehicles/{vehicle_id}/documents",
        json=document_payload(
            document_type="invoice",
            storage_key="vehicles/ABC1D23/invoice.pdf",
            maintenance_record_id=record.json()["id"],
        ),
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["maintenance_record_id"] == record.json()["id"]


def test_duplicate_storage_key_returns_conflict(client: TestClient) -> None:
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    client.post(
        f"/api/v1/vehicles/{vehicle_id}/documents",
        json=document_payload(),
        headers=headers,
    )

    response = client.post(
        f"/api/v1/vehicles/{vehicle_id}/documents",
        json=document_payload(document_type="invoice"),
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Document storage key already registered"


def test_list_and_read_vehicle_documents(client: TestClient) -> None:
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    created = client.post(
        f"/api/v1/vehicles/{vehicle_id}/documents",
        json=document_payload(),
        headers=headers,
    )
    document_id = created.json()["id"]

    list_response = client.get(f"/api/v1/vehicles/{vehicle_id}/documents", headers=headers)
    read_response = client.get(f"/api/v1/documents/{document_id}", headers=headers)

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert read_response.status_code == 200
    assert "file_content" not in read_response.json()
