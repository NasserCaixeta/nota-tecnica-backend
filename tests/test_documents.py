from fastapi.testclient import TestClient

from app.integrations.storage.r2 import PresignedUpload
from app.modules.documents.router import get_storage_client
from tests.test_maintenance import auth_headers, create_vehicle, maintenance_payload


class FakeStorageClient:
    def create_presigned_upload_url(
        self,
        storage_key: str,
        content_type: str,
        expires_seconds: int,
    ) -> PresignedUpload:
        return PresignedUpload(
            upload_url=f"https://upload.example.test/{storage_key}",
            required_headers={"Content-Type": content_type},
        )


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
    assert data["upload_status"] == "uploaded"
    assert data["processing_status"] == "not_requested"
    assert data["original_file_name"] == "crlv.pdf"
    assert data["uploaded_at"] is not None


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


def test_linked_user_can_create_document_upload_intent(client: TestClient) -> None:
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    client.app.dependency_overrides[get_storage_client] = lambda: (lambda: FakeStorageClient())

    response = client.post(
        f"/api/v1/vehicles/{vehicle_id}/documents/upload-intents",
        json={
            "document_type": "crlv",
            "file_name": "crlv.pdf",
            "content_type": "application/pdf",
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["document"]["upload_status"] == "pending"
    assert data["document"]["processing_status"] == "not_requested"
    assert data["document"]["review_status"] == "pending"
    assert data["document"]["storage_key"].startswith("vehicles/ABC1D23/documents/")
    assert data["storage_key"] == data["document"]["storage_key"]
    assert data["upload_url"].startswith("https://upload.example.test/")
    assert data["required_headers"] == {"Content-Type": "application/pdf"}


def test_unlinked_user_cannot_create_document_upload_intent(client: TestClient) -> None:
    owner_headers = auth_headers(client)
    vehicle_id = create_vehicle(client, owner_headers)
    other_headers = auth_headers(client, email="other@example.com", cpf="39053344705")
    client.app.dependency_overrides[get_storage_client] = lambda: (lambda: FakeStorageClient())

    response = client.post(
        f"/api/v1/vehicles/{vehicle_id}/documents/upload-intents",
        json={
            "document_type": "crlv",
            "file_name": "crlv.pdf",
            "content_type": "application/pdf",
        },
        headers=other_headers,
    )

    assert response.status_code == 404


def test_upload_intent_rejects_unsupported_content_type(client: TestClient) -> None:
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)

    response = client.post(
        f"/api/v1/vehicles/{vehicle_id}/documents/upload-intents",
        json={
            "document_type": "crlv",
            "file_name": "crlv.exe",
            "content_type": "application/x-msdownload",
        },
        headers=headers,
    )

    assert response.status_code == 422


def create_upload_intent(
    client: TestClient,
    vehicle_id: int,
    headers: dict[str, str],
) -> dict[str, object]:
    client.app.dependency_overrides[get_storage_client] = lambda: (lambda: FakeStorageClient())
    response = client.post(
        f"/api/v1/vehicles/{vehicle_id}/documents/upload-intents",
        json={
            "document_type": "crlv",
            "file_name": "crlv.pdf",
            "content_type": "application/pdf",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["document"]


def test_linked_user_can_confirm_document_upload(client: TestClient) -> None:
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    document = create_upload_intent(client, vehicle_id, headers)

    response = client.post(
        f"/api/v1/documents/{document['id']}/confirm-upload",
        json={"file_size_bytes": 12345},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["upload_status"] == "uploaded"
    assert data["processing_status"] == "pending"
    assert data["file_size_bytes"] == 12345
    assert data["uploaded_at"] is not None


def test_unlinked_user_cannot_confirm_document_upload(client: TestClient) -> None:
    owner_headers = auth_headers(client)
    vehicle_id = create_vehicle(client, owner_headers)
    document = create_upload_intent(client, vehicle_id, owner_headers)
    other_headers = auth_headers(client, email="other@example.com", cpf="39053344705")

    response = client.post(
        f"/api/v1/documents/{document['id']}/confirm-upload",
        json={},
        headers=other_headers,
    )

    assert response.status_code == 404
