from app.core.config import Settings
from app.integrations.queue.celery_app import create_celery_app
from app.integrations.storage.r2 import create_r2_config


def test_r2_config_can_be_created_from_settings() -> None:
    settings = Settings(
        _env_file=None,
        R2_ACCOUNT_ID="account",
        R2_ACCESS_KEY_ID="access",
        R2_SECRET_ACCESS_KEY="secret",
        R2_BUCKET_NAME="bucket",
        R2_ENDPOINT_URL="https://example.r2.cloudflarestorage.com",
    )

    config = create_r2_config(settings)

    assert config.account_id == "account"
    assert config.access_key_id == "access"
    assert config.bucket_name == "bucket"
    assert config.endpoint_url == "https://example.r2.cloudflarestorage.com"
    assert config.secret_access_key == "secret"
    assert "secret" not in repr(config)


def test_celery_app_uses_configured_redis_url() -> None:
    settings = Settings(_env_file=None, REDIS_URL="redis://redis.example:6379/3")

    celery_app = create_celery_app(settings)

    assert celery_app.conf.broker_url == "redis://redis.example:6379/3"
    assert celery_app.conf.result_backend == "redis://redis.example:6379/3"
