from fastapi.testclient import TestClient

from tests.support import register_approved_user as register_user
from tests.test_auth_users import login


def workshop_payload(
    *,
    cnpj: str = "04.252.011/0001-10",
    source: str = "user_submitted",
) -> dict[str, object]:
    return {
        "legal_name": "Oficina Central LTDA",
        "trade_name": "Oficina Central",
        "cnpj": cnpj,
        "phone": "+55 11 3333-0000",
        "email": "contato@oficinacentral.com",
        "zip_code": "01001-000",
        "street": "Rua da Oficina",
        "number": "500",
        "neighborhood": "Centro",
        "city": "Sao Paulo",
        "state": "sp",
        "complement": None,
        "specialties": ["mechanics", "oil_change"],
        "source": source,
    }


def token_for(
    client: TestClient,
    *,
    email: str,
    cpf: str,
    profile_type: str,
) -> str:
    register_user(client, email=email, cpf=cpf, profile_type=profile_type)
    return login(client, email=email)


def test_customer_can_create_user_submitted_workshop(client: TestClient) -> None:
    token = token_for(
        client,
        email="customer@example.com",
        cpf="52998224725",
        profile_type="customer",
    )

    response = client.post(
        "/api/v1/workshops",
        json=workshop_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["cnpj"] == "04252011000110"
    assert data["source"] == "user_submitted"
    assert data["verification_status"] == "pending"


def test_workshop_owner_can_create_owner_claimed_workshop(client: TestClient) -> None:
    token = token_for(
        client,
        email="owner@example.com",
        cpf="39053344705",
        profile_type="workshop_owner",
    )

    response = client.post(
        "/api/v1/workshops",
        json=workshop_payload(source="owner_claimed"),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["source"] == "owner_claimed"

    managed = client.get("/api/v1/workshops/me", headers={"Authorization": f"Bearer {token}"})
    assert managed.status_code == 200
    assert managed.json() == []
    claims = client.get("/api/v1/workshops/claims/me", headers={"Authorization": f"Bearer {token}"})
    assert claims.status_code == 200
    assert len(claims.json()) == 1


def test_customer_can_request_workshop_representation_without_changing_profile(
    client: TestClient,
) -> None:
    token = token_for(
        client,
        email="customer@example.com",
        cpf="52998224725",
        profile_type="customer",
    )

    response = client.post(
        "/api/v1/workshops",
        json=workshop_payload(source="owner_claimed"),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["verification_status"] == "pending"


def test_duplicate_cnpj_returns_conflict(client: TestClient) -> None:
    token = token_for(
        client,
        email="customer@example.com",
        cpf="52998224725",
        profile_type="customer",
    )
    client.post(
        "/api/v1/workshops",
        json=workshop_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.post(
        "/api/v1/workshops",
        json=workshop_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Workshop CNPJ already registered"


def test_pending_workshop_is_not_a_public_verified_profile(client: TestClient) -> None:
    token = token_for(
        client,
        email="customer@example.com",
        cpf="52998224725",
        profile_type="customer",
    )
    created = client.post(
        "/api/v1/workshops",
        json=workshop_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    workshop_id = created.json()["id"]

    list_response = client.get("/api/v1/workshops")
    detail_response = client.get(f"/api/v1/workshops/{workshop_id}")

    assert list_response.status_code == 200
    assert list_response.json() == []
    assert detail_response.status_code == 404


def test_create_workshop_rejects_invalid_cnpj(client: TestClient) -> None:
    token = token_for(
        client,
        email="customer@example.com",
        cpf="52998224725",
        profile_type="customer",
    )

    response = client.post(
        "/api/v1/workshops",
        json=workshop_payload(cnpj="12.345.678/0001-90"),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
