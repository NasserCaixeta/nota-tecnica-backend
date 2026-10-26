from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.modules.documents.router import get_storage_client
from tests.test_documents import FakeStorageClient, create_upload_intent, document_payload
from tests.test_maintenance import auth_headers, create_vehicle, maintenance_payload
from tests.test_vehicles import vehicle_payload


class InspectableStorage(FakeStorageClient):
    def __init__(self, *, exists=True, size=12345, content_type="application/pdf"):
        self.info = SimpleNamespace(
            exists=exists, size_bytes=size, content_type=content_type, etag='"original-etag"'
        )

    def inspect_object(self, storage_key):
        return self.info

    def finalize_upload(self, storage_key, etag):
        return f"verified/{storage_key}"

    def create_presigned_download_url(self, storage_key, expires_seconds):
        return f"https://download.example.test/{storage_key}?expires={expires_seconds}"


def install_storage(client, storage):
    client.app.dependency_overrides[get_storage_client] = lambda: lambda: storage


def test_shared_plate_does_not_grant_document_access(client):
    owner = auth_headers(client)
    vehicle_id = create_vehicle(client, owner)
    document = create_upload_intent(client, vehicle_id, owner)
    other = auth_headers(client, email="other@example.com", cpf="39053344705")
    linked = client.post("/api/v1/garage/vehicles", headers=other, json=vehicle_payload())
    assert linked.status_code == 201
    for suffix, method in [("", "get"), ("/download", "get"), ("/confirm-upload", "post")]:
        response = getattr(client, method)(
            f"/api/v1/documents/{document['id']}{suffix}",
            headers=other,
            **({"json": {}} if method == "post" else {}),
        )
        assert response.status_code == 404
    listed = client.get(f"/api/v1/vehicles/{vehicle_id}/documents", headers=other)
    assert listed.status_code == 200
    assert listed.json() == []


@pytest.mark.parametrize(
    "storage,expected",
    [
        (InspectableStorage(exists=False), 409),
        (InspectableStorage(size=10 * 1024 * 1024 + 1), 422),
        (InspectableStorage(content_type="application/octet-stream"), 422),
    ],
)
def test_confirmation_requires_a_real_valid_object(client, storage, expected):
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    document = create_upload_intent(client, vehicle_id, headers)
    install_storage(client, storage)
    confirmed = client.post(
        f"/api/v1/documents/{document['id']}/confirm-upload", headers=headers, json={}
    )
    assert confirmed.status_code == expected
    stored = client.get(f"/api/v1/documents/{document['id']}", headers=headers)
    assert stored.json()["upload_status"] == "pending"


def test_download_is_private_short_lived_and_uses_finalized_object(client):
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    document = create_upload_intent(client, vehicle_id, headers)
    install_storage(client, InspectableStorage())
    confirmed = client.post(
        f"/api/v1/documents/{document['id']}/confirm-upload", headers=headers, json={}
    )
    assert confirmed.status_code == 200
    assert "storage_key" not in confirmed.json()
    before = datetime.now(UTC)
    downloaded = client.get(f"/api/v1/documents/{document['id']}/download", headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.json()["url"].startswith("https://download.example.test/verified/")
    expiry = datetime.fromisoformat(downloaded.json()["expires_at"])
    assert 299 <= (expiry - before).total_seconds() <= 301
    repeated = client.post(
        f"/api/v1/documents/{document['id']}/confirm-upload", headers=headers, json={}
    )
    assert repeated.status_code == 200
    assert repeated.json()["uploaded_at"] == confirmed.json()["uploaded_at"]


def test_legacy_storage_key_registration_is_not_an_upload(client):
    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    response = client.post(
        f"/api/v1/vehicles/{vehicle_id}/documents", headers=headers, json=document_payload()
    )
    assert response.status_code == 410


async def test_legacy_uploaded_marker_is_not_proof_of_verified_storage(client, db_session):
    from app.modules.documents.models import Document, DocumentUploadStatus

    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    data = create_upload_intent(client, vehicle_id, headers)
    document = await db_session.get(Document, data["id"])
    document.upload_status = DocumentUploadStatus.UPLOADED
    await db_session.commit()
    install_storage(client, InspectableStorage())
    response = client.get(f"/api/v1/documents/{document.id}/download", headers=headers)
    assert response.status_code == 409


def test_shared_vehicle_does_not_allow_attaching_to_another_authors_service(client):
    owner = auth_headers(client)
    vehicle_id = create_vehicle(client, owner)
    record = client.post(
        f"/api/v1/vehicles/{vehicle_id}/maintenance-records",
        headers=owner,
        json=maintenance_payload(),
    ).json()
    other = auth_headers(client, email="other@example.com", cpf="39053344705")
    client.post("/api/v1/garage/vehicles", headers=other, json=vehicle_payload())
    install_storage(client, InspectableStorage())
    attached = client.post(
        f"/api/v1/vehicles/{vehicle_id}/documents/upload-intents",
        headers=other,
        json={
            "document_type": "invoice",
            "file_name": "invoice.pdf",
            "content_type": "application/pdf",
            "maintenance_record_id": record["id"],
        },
    )
    assert attached.status_code == 404


def test_unavailable_storage_configuration_returns_a_recoverable_error(client):
    from fastapi.testclient import TestClient

    from app.integrations.storage.r2 import R2ConfigurationError

    headers = auth_headers(client)
    vehicle_id = create_vehicle(client, headers)
    document = create_upload_intent(client, vehicle_id, headers)

    def unavailable():
        raise R2ConfigurationError("Missing test configuration")

    client.app.dependency_overrides[get_storage_client] = lambda: unavailable
    with TestClient(client.app, raise_server_exceptions=False) as unavailable_client:
        response = unavailable_client.post(
            f"/api/v1/documents/{document['id']}/confirm-upload", headers=headers, json={}
        )
    assert response.status_code == 503
