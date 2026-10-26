from tests.test_documents import FakeStorageClient
from tests.test_maintenance import auth_headers
from tests.test_participation_admin import admin_headers
from tests.test_workshops import workshop_payload


def create_reference(client, headers):
    response = client.post("/api/v1/workshops", headers=headers, json=workshop_payload())
    assert response.status_code == 201
    return response.json()


def test_reference_workshop_does_not_grant_management_or_public_verification(client):
    headers = auth_headers(client)
    office = create_reference(client, headers)
    assert client.get("/api/v1/workshops/me", headers=headers).json() == []
    assert client.get(f"/api/v1/workshops/{office['id']}").status_code == 404


async def test_one_account_can_be_customer_and_approved_workshop_responsible(client, db_session):
    from app.modules.workshops.claims_router import get_storage_client

    owner = auth_headers(client)
    office = create_reference(client, owner)
    requested = client.post(f"/api/v1/workshops/{office['id']}/claims", headers=owner)
    assert requested.status_code == 201, requested.text
    claim = requested.json()
    assert client.get("/api/v1/workshops/me", headers=owner).json() == []
    assert client.get("/api/v1/users/me", headers=owner).json()["capabilities"] == ["customer"]
    client.app.dependency_overrides[get_storage_client] = lambda: lambda: FakeStorageClient()
    documents = []
    for kind in ("company_contract_or_power_of_attorney", "representative_identity"):
        intent = client.post(
            f"/api/v1/workshop-claims/{claim['id']}/documents/upload-intents",
            headers=owner,
            json={
                "document_type": "other",
                "validation_document_type": kind,
                "file_name": "proof.pdf",
                "content_type": "application/pdf",
            },
        )
        assert intent.status_code == 201, intent.text
        document = intent.json()["document"]
        from app.modules.documents.router import get_storage_client as document_storage

        client.app.dependency_overrides[document_storage] = lambda: lambda: FakeStorageClient()
        confirmed = client.post(
            f"/api/v1/documents/{document['id']}/confirm-upload", headers=owner, json={}
        )
        assert confirmed.status_code == 200
        documents.append(document)
    admin = await admin_headers(client, db_session)
    early = client.patch(
        f"/api/v1/admin/workshop-claims/{claim['id']}/review",
        headers=admin,
        json={"decision": "verified", "expected_version": 1, "reason": "Review"},
    )
    assert early.status_code == 409
    for document in documents:
        reviewed = client.patch(
            f"/api/v1/admin/documents/{document['id']}/review",
            headers=admin,
            json={"review_status": "approved", "expected_version": 1},
        )
        assert reviewed.status_code == 200
    current = client.get("/api/v1/workshops/claims/me", headers=owner).json()[0]
    approved = client.patch(
        f"/api/v1/admin/workshop-claims/{claim['id']}/review",
        headers=admin,
        json={
            "decision": "verified",
            "expected_version": current["review_version"],
            "reason": "Representation verified",
        },
    )
    assert approved.status_code == 200, approved.text
    assert set(client.get("/api/v1/users/me", headers=owner).json()["capabilities"]) == {
        "customer",
        "workshop_owner",
    }
    assert len(client.get("/api/v1/workshops/me", headers=owner).json()) == 1
    assert client.get(f"/api/v1/workshops/{office['id']}").status_code == 200
    assert len(client.get("/api/v1/workshops").json()) == 1
    other = auth_headers(client, email="other@example.com", cpf="39053344705")
    assert client.get(f"/api/v1/documents/{documents[0]['id']}", headers=other).status_code == 404
    competing = client.post(f"/api/v1/workshops/{office['id']}/claims", headers=other)
    assert competing.status_code == 201
    assert client.get("/api/v1/workshops/me", headers=other).json() == []
    assert len(client.get("/api/v1/workshops").json()) == 1


def test_customer_can_request_owner_claimed_workshop_without_an_exclusive_profile(client):
    headers = auth_headers(client)
    response = client.post(
        "/api/v1/workshops", headers=headers, json=workshop_payload(source="owner_claimed")
    )
    assert response.status_code == 201
    assert client.get("/api/v1/workshops/me", headers=headers).json() == []
    assert len(client.get("/api/v1/workshops/claims/me", headers=headers).json()) == 1


async def test_admin_cannot_approve_own_workshop_representation(client, db_session):
    headers = await admin_headers(client, db_session)
    office = create_reference(client, headers)
    claim = client.post(f"/api/v1/workshops/{office['id']}/claims", headers=headers)
    assert claim.status_code == 201
    response = client.patch(
        f"/api/v1/admin/workshop-claims/{claim.json()['id']}/review",
        headers=headers,
        json={"decision": "verified", "expected_version": 1, "reason": "Own claim"},
    )
    assert response.status_code == 409
