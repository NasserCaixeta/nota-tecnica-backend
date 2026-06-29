from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.security import verify_password
from app.modules.users.models import User, UserProfileType


def user_payload(
    *,
    email: str = "driver@example.com",
    cpf: str = "123.456.789-01",
    profile_type: str = "customer",
) -> dict[str, object]:
    return {
        "full_name": "Maria Driver",
        "email": email,
        "password": "strong-password",
        "cpf": cpf,
        "phone": "+55 11 99999-0000",
        "birth_date": "1990-01-20",
        "profile_type": profile_type,
        "zip_code": "01001-000",
        "street": "Rua Central",
        "number": "100",
        "neighborhood": "Centro",
        "city": "Sao Paulo",
        "state": "sp",
        "complement": "Apto 10",
    }


def register_user(client: TestClient, **overrides: object) -> dict[str, object]:
    payload = user_payload(**overrides)
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, email: str = "driver@example.com") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "strong-password"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_register_customer_returns_user_without_password(client: TestClient) -> None:
    data = register_user(client)

    assert data["email"] == "driver@example.com"
    assert data["cpf"] == "12345678901"
    assert data["profile_type"] == "customer"
    assert data["state"] == "SP"
    assert "password" not in data
    assert "password_hash" not in data


def test_register_workshop_owner(client: TestClient) -> None:
    data = register_user(
        client,
        email="owner@example.com",
        cpf="987.654.321-00",
        profile_type="workshop_owner",
    )

    assert data["profile_type"] == "workshop_owner"


def test_register_rejects_admin(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json=user_payload(profile_type="admin"))

    assert response.status_code == 400
    assert response.json()["detail"] == "Public registration cannot create admin users"


def test_register_duplicate_email_returns_conflict(client: TestClient) -> None:
    register_user(client)

    response = client.post(
        "/api/v1/auth/register",
        json=user_payload(cpf="22233344455"),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_register_duplicate_cpf_returns_conflict(client: TestClient) -> None:
    register_user(client)

    response = client.post(
        "/api/v1/auth/register",
        json=user_payload(email="other@example.com"),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "CPF already registered"


async def test_password_is_hashed(db_session: AsyncSession, client: TestClient) -> None:
    register_user(client)

    result = await db_session.execute(select(User).where(User.email == "driver@example.com"))
    user = result.scalar_one()

    assert user.password_hash != "strong-password"
    assert verify_password("strong-password", user.password_hash)


def test_login_returns_access_token(client: TestClient) -> None:
    register_user(client)

    token = login(client)

    assert isinstance(token, str)
    assert token


def test_login_invalid_password_returns_unauthorized(client: TestClient) -> None:
    register_user(client)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "driver@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_users_me_requires_token(client: TestClient) -> None:
    response = client.get("/api/v1/users/me")

    assert response.status_code == 401


def test_users_me_returns_authenticated_user(client: TestClient) -> None:
    register_user(client)
    token = login(client)

    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "driver@example.com"
    assert response.json()["profile_type"] == UserProfileType.CUSTOMER.value
