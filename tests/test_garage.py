from fastapi.testclient import TestClient

from app.integrations.storage.r2 import PresignedUpload
from app.modules.documents.models import ValidationDocumentType
from app.modules.garage.requirements import required_documents_for_relationship
from app.modules.garage.router import get_storage_client
from app.modules.garage.service import build_garage_permissions
from app.modules.vehicles.models import GarageValidationStatus, VehicleRelationshipType
from tests.test_maintenance import auth_headers, maintenance_payload
from tests.test_vehicles import vehicle_payload


def test_garage_relationship_types_exclude_buyer_interested() -> None:
    assert VehicleRelationshipType.OWNER.value == "owner"
    assert VehicleRelationshipType.SPOUSE.value == "spouse"
    assert VehicleRelationshipType.FAMILY.value == "family"
    assert VehicleRelationshipType.COMPANY_REPRESENTATIVE.value == "company_representative"
    assert VehicleRelationshipType.FLEET_RESPONSIBLE.value == "fleet_responsible"
    assert VehicleRelationshipType.RECENT_BUYER.value == "recent_buyer"
    assert VehicleRelationshipType.AUTHORIZED_DRIVER.value == "authorized_driver"
    assert VehicleRelationshipType.OTHER.value == "other"
    assert "buyer_interested" not in {item.value for item in VehicleRelationshipType}


def test_required_documents_for_owner() -> None:
    assert required_documents_for_relationship(VehicleRelationshipType.OWNER) == [
        ValidationDocumentType.CRLV
    ]


def test_required_documents_for_company_representative() -> None:
    assert required_documents_for_relationship(
        VehicleRelationshipType.COMPANY_REPRESENTATIVE
    ) == [
        ValidationDocumentType.CRLV,
        ValidationDocumentType.COMPANY_CONTRACT_OR_POWER_OF_ATTORNEY,
        ValidationDocumentType.REPRESENTATIVE_IDENTITY,
    ]


def test_required_documents_for_all_garage_relationships_are_defined() -> None:
    for relationship_type in VehicleRelationshipType:
        assert required_documents_for_relationship(relationship_type)


def test_pending_documents_permissions() -> None:
    permissions = build_garage_permissions(
        GarageValidationStatus.PENDING_DOCUMENTS,
        can_submit_review=True,
    )

    assert permissions.can_add_maintenance is True
    assert permissions.can_upload_documents is True
    assert permissions.can_submit_review is True
    assert permissions.can_share_history is False
    assert permissions.can_generate_sale_report is False


def test_payment_required_permissions_are_blocked() -> None:
    permissions = build_garage_permissions(
        GarageValidationStatus.PAYMENT_REQUIRED,
        can_submit_review=True,
    )

    assert permissions.can_add_maintenance is False
    assert permissions.can_upload_documents is False
    assert permissions.can_submit_review is False
    assert permissions.can_share_history is False
    assert permissions.can_generate_sale_report is False


def test_active_permissions_allow_share_and_report() -> None:
    permissions = build_garage_permissions(
        GarageValidationStatus.ACTIVE,
        can_submit_review=False,
    )

    assert permissions.can_add_maintenance is True
    assert permissions.can_upload_documents is False
    assert permissions.can_submit_review is False
    assert permissions.can_share_history is True
    assert permissions.can_generate_sale_report is True


def test_first_garage_vehicle_starts_pending_documents(client: TestClient) -> None:
    headers = auth_headers(client)

    response = client.post(
        "/api/v1/garage/vehicles",
        json={**vehicle_payload(), "relationship_type": "owner"},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["garage_status"] == "pending_documents"
    assert data["relationship_type"] == "owner"
    assert data["permissions"]["can_add_maintenance"] is True
    assert data["permissions"]["can_upload_documents"] is True
    assert data["documents"]["missing"] == ["crlv"]


def test_second_garage_vehicle_requires_payment(client: TestClient) -> None:
    headers = auth_headers(client)
    first = client.post(
        "/api/v1/garage/vehicles",
        json={**vehicle_payload(), "relationship_type": "owner"},
        headers=headers,
    )
    assert first.status_code == 201

    response = client.post(
        "/api/v1/garage/vehicles",
        json={
            **vehicle_payload(
                plate="DEF2E34",
                chassis="9BWZZZ377VT004252",
                renavam="98765432100",
            ),
            "relationship_type": "owner",
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["garage_status"] == "payment_required"
    assert data["permissions"]["can_add_maintenance"] is False
    assert data["permissions"]["can_upload_documents"] is False


def test_garage_dashboard_returns_summary_and_empty_alerts(client: TestClient) -> None:
    headers = auth_headers(client)
    client.post(
        "/api/v1/garage/vehicles",
        json={**vehicle_payload(), "relationship_type": "owner"},
        headers=headers,
    )

    response = client.get("/api/v1/garage", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total"] == 1
    assert data["summary"]["pending_documents"] == 1
    assert data["summary"]["has_free_vehicle_slot"] is False
    assert data["vehicles"][0]["maintenance_alerts"] == []
    assert "recommended_workshops" in data["vehicles"][0]


def test_garage_vehicle_detail_requires_link(client: TestClient) -> None:
    owner_headers = auth_headers(client)
    created = client.post(
        "/api/v1/garage/vehicles",
        json={**vehicle_payload(), "relationship_type": "owner"},
        headers=owner_headers,
    )
    vehicle_id = created.json()["vehicle_id"]
    other_headers = auth_headers(client, email="other@example.com", cpf="39053344705")

    response = client.get(f"/api/v1/garage/vehicles/{vehicle_id}", headers=other_headers)

    assert response.status_code == 404


def test_can_update_relationship_before_review(client: TestClient) -> None:
    headers = auth_headers(client)
    created = client.post(
        "/api/v1/garage/vehicles",
        json={**vehicle_payload(), "relationship_type": "owner"},
        headers=headers,
    )
    link_id = created.json()["vehicle_link_id"]

    response = client.patch(
        f"/api/v1/garage/vehicle-links/{link_id}/relationship",
        json={"relationship_type": "spouse", "relationship_note": "Vehicle belongs to spouse"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["relationship_type"] == "spouse"
    assert data["documents"]["missing"] == [
        "crlv",
        "owner_authorization",
        "relationship_proof",
    ]


def test_submit_review_without_required_documents_fails(client: TestClient) -> None:
    headers = auth_headers(client)
    created = client.post(
        "/api/v1/garage/vehicles",
        json={**vehicle_payload(), "relationship_type": "owner"},
        headers=headers,
    )
    link_id = created.json()["vehicle_link_id"]

    response = client.post(
        f"/api/v1/garage/vehicle-links/{link_id}/submit-review",
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Required validation documents are missing"


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


def upload_validation_document(
    client: TestClient,
    link_id: int,
    headers: dict[str, str],
    validation_document_type: str,
) -> dict[str, object]:
    client.app.dependency_overrides[get_storage_client] = lambda: (lambda: FakeStorageClient())
    response = client.post(
        f"/api/v1/garage/vehicle-links/{link_id}/documents/upload-intents",
        json={
            "document_type": "crlv",
            "validation_document_type": validation_document_type,
            "file_name": f"{validation_document_type}.pdf",
            "content_type": "application/pdf",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    document = response.json()["document"]
    confirm = client.post(
        f"/api/v1/documents/{document['id']}/confirm-upload",
        json={"file_size_bytes": 1234},
        headers=headers,
    )
    assert confirm.status_code == 200, confirm.text
    return confirm.json()


def test_submit_review_with_required_document_goes_under_review(
    client: TestClient,
) -> None:
    headers = auth_headers(client)
    created = client.post(
        "/api/v1/garage/vehicles",
        json={**vehicle_payload(), "relationship_type": "owner"},
        headers=headers,
    )
    link_id = created.json()["vehicle_link_id"]
    upload_validation_document(client, link_id, headers, "crlv")

    response = client.post(
        f"/api/v1/garage/vehicle-links/{link_id}/submit-review",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["garage_status"] == "under_review"


def test_payment_required_vehicle_cannot_add_maintenance(client: TestClient) -> None:
    headers = auth_headers(client)
    client.post(
        "/api/v1/garage/vehicles",
        json={**vehicle_payload(), "relationship_type": "owner"},
        headers=headers,
    )
    second = client.post(
        "/api/v1/garage/vehicles",
        json={
            **vehicle_payload(
                plate="DEF2E34",
                chassis="9BWZZZ377VT004252",
                renavam="98765432100",
            ),
            "relationship_type": "owner",
        },
        headers=headers,
    )

    response = client.post(
        f"/api/v1/vehicles/{second.json()['vehicle_id']}/maintenance-records",
        json=maintenance_payload(),
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Garage status does not allow maintenance records"


def test_under_review_vehicle_can_add_private_maintenance(client: TestClient) -> None:
    headers = auth_headers(client)
    created = client.post(
        "/api/v1/garage/vehicles",
        json={**vehicle_payload(), "relationship_type": "owner"},
        headers=headers,
    )
    link_id = created.json()["vehicle_link_id"]
    upload_validation_document(client, link_id, headers, "crlv")
    client.post(f"/api/v1/garage/vehicle-links/{link_id}/submit-review", headers=headers)

    response = client.post(
        f"/api/v1/vehicles/{created.json()['vehicle_id']}/maintenance-records",
        json=maintenance_payload(),
        headers=headers,
    )

    assert response.status_code == 201, response.text
