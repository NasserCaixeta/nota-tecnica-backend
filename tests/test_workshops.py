from fastapi.testclient import TestClient

from tests.test_auth_users import login, register_user


def workshop_payload(
    *,
    cnpj: str = "12.345.678/0001-90",
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
        cpf="12345678901",
        profile_type="customer",
    )

    response = client.post(
        "/api/v1/workshops",
        json=workshop_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["cnpj"] == "12345678000190"
    assert data["source"] == "user_submitted"
    assert data["verification_status"] == "pending"


def test_workshop_owner_can_create_owner_claimed_workshop(client: TestClient) -> None:
    token = token_for(
        client,
        email="owner@example.com",
        cpf="98765432100",
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
    assert len(managed.json()) == 1
    assert managed.json()[0]["role"] == "owner"
    assert managed.json()[0]["verification_status"] == "pending"


def test_customer_cannot_create_owner_claimed_workshop(client: TestClient) -> None:
    token = token_for(
        client,
        email="customer@example.com",
        cpf="12345678901",
        profile_type="customer",
    )

    response = client.post(
        "/api/v1/workshops",
        json=workshop_payload(source="owner_claimed"),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Only workshop owners can claim a workshop"


def test_duplicate_cnpj_returns_conflict(client: TestClient) -> None:
    token = token_for(
        client,
        email="customer@example.com",
        cpf="12345678901",
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


def test_public_workshop_list_and_detail(client: TestClient) -> None:
    token = token_for(
        client,
        email="customer@example.com",
        cpf="12345678901",
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
    assert len(list_response.json()) == 1
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == workshop_id
