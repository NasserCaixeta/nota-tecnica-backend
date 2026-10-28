import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.rate_limit import enforce_rate_limit, get_rate_limit_backend
from tests.test_auth_users import user_payload


class ClockCounter:
    def __init__(self):
        self.now = 0
        self.values = {}

    async def increment(self, key, window):
        count, expiry = self.values.get(key, (0, self.now + window))
        if self.now >= expiry:
            count, expiry = 0, self.now + window
        self.values[key] = count + 1, expiry
        return count + 1, max(1, expiry - self.now)


@pytest.fixture
def counter(client):
    instance = ClockCounter()
    client.app.dependency_overrides[get_rate_limit_backend] = lambda: instance
    return instance


def test_registration_has_ip_budget_before_inserting_another_account(client, counter, monkeypatch):
    monkeypatch.setenv("REGISTER_RATE_LIMIT", "2")
    get_settings.cache_clear()
    assert client.post("/api/v1/auth/register", json=user_payload()).status_code == 201
    assert client.post("/api/v1/auth/register", json=user_payload()).status_code == 409
    result = client.post(
        "/api/v1/auth/register", json=user_payload(email="other@example.com", cpf="39053344705")
    )
    assert result.status_code == 429
    assert int(result.headers["Retry-After"]) > 0


def test_login_budget_uses_normalized_identity(client, counter, monkeypatch):
    monkeypatch.setenv("LOGIN_IDENTITY_RATE_LIMIT", "2")
    monkeypatch.setenv("LOGIN_IP_RATE_LIMIT", "100")
    get_settings.cache_clear()
    for email in ["missing@example.com", "MISSING@example.com"]:
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": email, "password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "missing@example.com", "password": "wrong"}
        ).status_code
        == 429
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "different@example.com", "password": "wrong"}
        ).status_code
        == 401
    )
    assert all("missing@example.com" not in key for key in counter.values)


def test_public_queries_enforce_budget_and_reset_after_window(client, counter, monkeypatch):
    monkeypatch.setenv("QUERY_RATE_LIMIT", "2")
    get_settings.cache_clear()
    url = "/api/v1/public/vehicles/ABC1D23/history-preview"
    assert client.get(url).status_code == 200
    assert client.get(url).status_code == 200
    assert client.get(url).status_code == 429
    counter.now += 61
    assert client.get(url).status_code == 200


async def test_counter_scopes_and_identities_are_isolated():
    counter = ClockCounter()
    await enforce_rate_limit("a", "one@example.com", 1, 10, backend=counter)
    with pytest.raises(HTTPException) as error:
        await enforce_rate_limit("a", "one@example.com", 1, 10, backend=counter)
    assert error.value.status_code == 429
    await enforce_rate_limit("b", "one@example.com", 1, 10, backend=counter)
    await enforce_rate_limit("a", "two@example.com", 1, 10, backend=counter)


def test_invitation_budget_is_per_responsible_account(client, counter, monkeypatch):
    from tests.test_service_invitations import issue_invitation, workshop_service

    monkeypatch.setenv("INVITATION_SECRET_KEY", "test-invitation-key-with-at-least-32-characters")
    monkeypatch.setenv("INVITATION_RATE_LIMIT", "2")
    get_settings.cache_clear()
    office, record = workshop_service(client)
    issue_invitation(client, office, record)
    issue_invitation(client, office, record)
    response = client.post(
        f"/api/v1/maintenance-records/{record['id']}/invitations",
        headers=office,
        json={"revision_id": record["current_revision_id"], "recipient_email": "other@example.com"},
    )
    assert response.status_code == 429
