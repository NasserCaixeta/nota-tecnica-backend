from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.security import hash_password
from app.modules.users.models import User, UserProfileType
from tests.test_auth_users import login
from tests.test_documents import document_payload
from tests.test_maintenance import auth_headers, create_vehicle


async def create_admin_user(db_session: AsyncSession) -> None:
    admin = User(
        full_name="Admin User",
        email="admin@example.com",
        password_hash=hash_password("strong-password"),
        cpf="99988877766",
        phone="+55 11 98888-7766",
        birth_date=date(1985, 1, 1),
        profile_type=UserProfileType.ADMIN,
        zip_code="01001-000",
        street="Rua Admin",
        number="1",
        neighborhood="Centro",
        city="Sao Paulo",
        state="SP",
        complement=None,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()


async def test_admin_can_verify_vehicle_link(
    client: TestClient,
    db_session: AsyncSession,
) -> None:
    user_headers = auth_headers(client)
    vehicle_id = create_vehicle(client, user_headers)
    vehicle = client.get(f"/api/v1/vehicles/{vehicle_id}", headers=user_headers).json()
    await create_admin_user(db_session)
    admin_token = login(client, email="admin@example.com")

    response = client.patch(
        f"/api/v1/admin/vehicle-links/{vehicle['vehicle_link_id']}/verification",
        json={"verification_status": "verified"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["verification_status"] == "verified"
    assert response.json()["verification_rejection_reason"] is None


async def test_admin_can_reject_document(
    client: TestClient,
    db_session: AsyncSession,
) -> None:
    user_headers = auth_headers(client)
    vehicle_id = create_vehicle(client, user_headers)
    document = client.post(
        f"/api/v1/vehicles/{vehicle_id}/documents",
        json=document_payload(),
        headers=user_headers,
    ).json()
    await create_admin_user(db_session)
    admin_token = login(client, email="admin@example.com")

    response = client.patch(
        f"/api/v1/admin/documents/{document['id']}/review",
        json={"review_status": "rejected", "rejection_reason": "Unreadable document"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["review_status"] == "rejected"
    assert response.json()["rejection_reason"] == "Unreadable document"
