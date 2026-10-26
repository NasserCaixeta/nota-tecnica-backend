from fastapi.testclient import TestClient

from app.integrations.storage.r2 import PresignedUpload, StoredObjectInfo
from app.modules.documents.router import get_storage_client
from tests.test_maintenance import auth_headers, create_vehicle, maintenance_payload


class FakeStorageClient:
    def __init__(self, size=12345):
        self.size = size

    def create_presigned_upload_url(self, storage_key, content_type, expires_seconds):
        return PresignedUpload(
            f"https://upload.example.test/{storage_key}", {"Content-Type": content_type}
        )

    def inspect_object(self, storage_key):
        return StoredObjectInfo(True, self.size, "application/pdf", '"test-etag"')

    def finalize_upload(self, storage_key, etag):
        return f"verified/{storage_key}"

    def create_presigned_download_url(self, storage_key, expires_seconds):
        return f"https://download.example.test/{storage_key}?expires={expires_seconds}"


def document_payload(**overrides):
    return {
        "document_type": "crlv",
        "file_name": "crlv.pdf",
        "content_type": "application/pdf",
        "storage_key": "vehicles/ABC1D23/crlv.pdf",
        **overrides,
    }


def create_upload_intent(client, vehicle_id, headers, **overrides):
    client.app.dependency_overrides[get_storage_client] = lambda: lambda: FakeStorageClient()
    response = client.post(
        f"/api/v1/vehicles/{vehicle_id}/documents/upload-intents",
        headers=headers,
        json={
            "document_type": "crlv",
            "file_name": "crlv.pdf",
            "content_type": "application/pdf",
            **overrides,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["document"]


def create_uploaded_document(client, vehicle_id, headers, **overrides):
    document = create_upload_intent(client, vehicle_id, headers, **overrides)
    response = client.post(
        f"/api/v1/documents/{document['id']}/confirm-upload", headers=headers, json={}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_linked_user_can_create_vehicle_document(client: TestClient):
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    document = create_uploaded_document(client, vehicle_id, headers)
    assert document["vehicle_id"] == vehicle_id
    assert document["document_type"] == "crlv"
    assert document["review_status"] == "pending"
    assert document["upload_status"] == "uploaded"
    assert document["processing_status"] == "not_requested"
    assert document["uploaded_at"] is not None
    assert "storage_key" not in document


def test_document_can_reference_same_vehicle_maintenance(client):
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    record = client.post(
        f"/api/v1/vehicles/{vehicle_id}/maintenance-records",
        headers=headers,
        json=maintenance_payload(),
    ).json()
    document = create_uploaded_document(
        client, vehicle_id, headers, document_type="invoice", maintenance_record_id=record["id"]
    )
    assert document["maintenance_record_id"] == record["id"]


def test_list_and_read_vehicle_documents(client):
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    document = create_uploaded_document(client, vehicle_id, headers)
    listed = client.get(f"/api/v1/vehicles/{vehicle_id}/documents", headers=headers)
    read = client.get(f"/api/v1/documents/{document['id']}", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert read.status_code == 200
    assert "file_content" not in read.json()
    assert "storage_key" not in read.json()


def test_linked_user_can_create_document_upload_intent(client):
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    client.app.dependency_overrides[get_storage_client] = lambda: lambda: FakeStorageClient()
    response = client.post(
        f"/api/v1/vehicles/{vehicle_id}/documents/upload-intents",
        headers=headers,
        json={"document_type": "crlv", "file_name": "crlv.pdf", "content_type": "application/pdf"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["document"]["upload_status"] == "pending"
    assert body["document"]["review_status"] == "pending"
    assert body["storage_key"].startswith("vehicles/ABC1D23/documents/")
    assert "storage_key" not in body["document"]
    assert body["required_headers"] == {"Content-Type": "application/pdf"}


def test_unlinked_user_cannot_create_document_upload_intent(client):
    owner = auth_headers(client)
    vehicle_id = create_vehicle(client, owner)
    other = auth_headers(client, email="other@example.com", cpf="39053344705")
    client.app.dependency_overrides[get_storage_client] = lambda: lambda: FakeStorageClient()
    response = client.post(
        f"/api/v1/vehicles/{vehicle_id}/documents/upload-intents",
        headers=other,
        json={"document_type": "crlv", "file_name": "crlv.pdf", "content_type": "application/pdf"},
    )
    assert response.status_code == 404


def test_upload_intent_rejects_unsupported_content_type(client):
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    response = client.post(
        f"/api/v1/vehicles/{vehicle_id}/documents/upload-intents",
        headers=headers,
        json={
            "document_type": "crlv",
            "file_name": "file.exe",
            "content_type": "application/x-msdownload",
        },
    )
    assert response.status_code == 422


def test_linked_user_can_confirm_document_upload(client):
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    document = create_upload_intent(client, vehicle_id, headers)
    response = client.post(
        f"/api/v1/documents/{document['id']}/confirm-upload",
        headers=headers,
        json={"file_size_bytes": 12345},
    )
    assert response.status_code == 200
    assert response.json()["file_size_bytes"] == 12345
    assert response.json()["upload_status"] == "uploaded"
    assert response.json()["processing_status"] == "not_requested"


def test_unlinked_user_cannot_confirm_document_upload(client):
    owner = auth_headers(client)
    vehicle_id = create_vehicle(client, owner)
    document = create_upload_intent(client, vehicle_id, owner)
    other = auth_headers(client, email="other@example.com", cpf="39053344705")
    response = client.post(
        f"/api/v1/documents/{document['id']}/confirm-upload", headers=other, json={}
    )
    assert response.status_code == 404
