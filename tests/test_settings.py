from pathlib import Path

import pytest

from app.core.config import Settings, get_settings

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


def test_settings_defaults_are_usable(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_settings_env(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.app_name == "Nota Tecnica API"
    assert settings.app_env == "local"
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.redis_url.startswith("redis://")


def test_settings_accept_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_settings_env(monkeypatch)

    settings = Settings(_env_file=None, APP_NAME="Custom API", APP_ENV="test", DEBUG=False)

    assert settings.app_name == "Custom API"
    assert settings.app_env == "test"
    assert settings.debug is False


def test_settings_reads_environment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_settings_env(monkeypatch)

    monkeypatch.setenv("APP_NAME", "Environment API")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://env_user:env_password@env-host:5432/env_db",
    )
    monkeypatch.setenv("REDIS_URL", "redis://env-redis:6379/1")

    settings = Settings(_env_file=None)

    assert settings.app_name == "Environment API"
    assert settings.app_env == "test"
    assert settings.debug is False
    assert (
        settings.database_url == "postgresql+asyncpg://env_user:env_password@env-host:5432/env_db"
    )
    assert settings.redis_url == "redis://env-redis:6379/1"


def test_get_settings_returns_cached_instance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    get_settings.cache_clear()
    monkeypatch.chdir(tmp_path)
    clear_settings_env(monkeypatch)
    monkeypatch.setenv("APP_NAME", "First API")

    try:
        first_settings = get_settings()
        monkeypatch.setenv("APP_NAME", "Second API")
        second_settings = get_settings()

        assert first_settings is second_settings
        assert second_settings.app_name == "First API"
    finally:
        get_settings.cache_clear()


def test_database_metadata_is_importable() -> None:
    from app.db.base import Base

    assert Base.metadata is not None


def test_get_engine_uses_configured_database_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.db.session import get_async_session_factory, get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_async_session_factory.cache_clear()
    monkeypatch.chdir(tmp_path)
    clear_settings_env(monkeypatch)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:pass@db.example:5432/appdb",
    )

    try:
        engine = get_engine()

        assert "db.example" in str(engine.url)
        assert engine.url.database == "appdb"
    finally:
        get_settings.cache_clear()
        get_async_session_factory.cache_clear()
        get_engine.cache_clear()


def test_async_session_factory_and_get_db_are_importable() -> None:
    from app.db.session import get_async_session_factory, get_db

    async_session_factory = get_async_session_factory(
        "postgresql+asyncpg://user:pass@db.example:5432/appdb"
    )

    assert async_session_factory is not None
    assert get_db is not None

    get_async_session_factory.cache_clear()


@pytest.mark.asyncio
async def test_dispose_engine_clears_cached_engine() -> None:
    from app.db.session import dispose_engine, get_async_session_factory, get_engine

    database_url = "postgresql+asyncpg://user:pass@db.example:5432/appdb"
    get_engine.cache_clear()
    get_async_session_factory.cache_clear()

    try:
        engine = get_engine(database_url)
        get_async_session_factory(database_url)

        await dispose_engine(database_url)

        assert get_engine(database_url) is not engine
    finally:
        get_async_session_factory.cache_clear()
        get_engine.cache_clear()
