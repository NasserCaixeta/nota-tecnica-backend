from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_only_configured_frontend_origin_gets_cors_headers(monkeypatch):
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", '["http://localhost:5173"]')
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            allowed = client.options(
                "/api/v1/users/me",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Authorization",
                },
            )
            denied = client.options(
                "/api/v1/users/me",
                headers={
                    "Origin": "https://unrelated.example",
                    "Access-Control-Request-Method": "GET",
                },
            )
        assert allowed.status_code == 200
        assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert "access-control-allow-origin" not in denied.headers
    finally:
        get_settings.cache_clear()
