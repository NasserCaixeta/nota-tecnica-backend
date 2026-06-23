import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings

SETTINGS_ENV_VARS = (
    "APP_NAME",
    "APP_ENV",
    "DEBUG",
    "API_V1_PREFIX",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "DATABASE_URL",
    "REDIS_URL",
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
    "R2_ENDPOINT_URL",
)


def clear_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_var in SETTINGS_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


def load_main_module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    clear_settings_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()

    if "app.main" in sys.modules:
        return importlib.reload(sys.modules["app.main"])

    return importlib.import_module("app.main")


def test_root_healthcheck_returns_app_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    main = load_main_module(monkeypatch, tmp_path)
    client = TestClient(main.create_app())

    try:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "app": "Nota Tecnica API",
            "environment": "local",
        }
    finally:
        get_settings.cache_clear()


def test_versioned_healthcheck_returns_app_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    main = load_main_module(monkeypatch, tmp_path)
    client = TestClient(main.create_app())

    try:
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "app": "Nota Tecnica API",
            "environment": "local",
        }
    finally:
        get_settings.cache_clear()


def test_app_registers_global_exception_handler(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    main = load_main_module(monkeypatch, tmp_path)

    try:
        monkeypatch.setenv("DEBUG", "false")
        get_settings.cache_clear()
        application = main.create_app()
        client = TestClient(application, raise_server_exceptions=False)

        @application.get("/boom")
        def boom() -> None:
            raise RuntimeError("boom")

        response = client.get("/boom")

        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}
    finally:
        get_settings.cache_clear()
