from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        hide_input_in_errors=True,
    )

    app_name: str = Field(default="Nota Tecnica API", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    debug: bool = Field(default=True, alias="DEBUG")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    backend_cors_origins: list[str] = Field(
        default=["http://localhost:5173"], alias="BACKEND_CORS_ORIGINS"
    )

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="nota_tecnica", alias="POSTGRES_DB")
    postgres_user: str = Field(default="nota_tecnica", alias="POSTGRES_USER")
    postgres_password: str = Field(default="nota_tecnica", alias="POSTGRES_PASSWORD")
    database_url: str = Field(
        default="postgresql+asyncpg://nota_tecnica:nota_tecnica@localhost:5432/nota_tecnica",
        alias="DATABASE_URL",
    )

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    invitation_secret_key: str = Field(default="", alias="INVITATION_SECRET_KEY")
    frontend_url: str = Field(default="http://localhost:5173", alias="FRONTEND_URL")

    payments_environment: Literal["sandbox"] = Field(
        default="sandbox", alias="PAYMENTS_ENVIRONMENT"
    )
    payments_enabled: bool = Field(default=False, alias="PAYMENTS_ENABLED")
    payments_history_price_cents: int | None = Field(
        default=None, gt=0, alias="PAYMENTS_HISTORY_PRICE_CENTS"
    )
    payments_subscription_price_cents: int | None = Field(
        default=None, gt=0, alias="PAYMENTS_SUBSCRIPTION_PRICE_CENTS"
    )
    payments_callback_base_url: str = Field(default="", alias="PAYMENTS_CALLBACK_BASE_URL")
    stripe_secret_key: SecretStr = Field(default=SecretStr(""), alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: SecretStr = Field(default=SecretStr(""), alias="STRIPE_WEBHOOK_SECRET")

    smtp_enabled: bool = Field(default=False, alias="SMTP_ENABLED")
    smtp_capture_only: bool = Field(default=True, alias="SMTP_CAPTURE_ONLY")
    smtp_host: str = Field(default="localhost", alias="SMTP_HOST")
    smtp_port: int = Field(default=1025, alias="SMTP_PORT")
    smtp_from_address: str = Field(default="piloto@nota-tecnica.local", alias="SMTP_FROM_ADDRESS")
    smtp_starttls: bool = Field(default=False, alias="SMTP_STARTTLS")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: SecretStr = Field(default=SecretStr(""), alias="SMTP_PASSWORD")

    recovery_secret_key: SecretStr = Field(default=SecretStr(""), alias="RECOVERY_SECRET_KEY")
    recovery_identity_limit: int = Field(default=3, gt=0, alias="RECOVERY_IDENTITY_LIMIT")
    recovery_ip_limit: int = Field(default=10, gt=0, alias="RECOVERY_IP_LIMIT")
    recovery_window_seconds: int = Field(default=900, gt=0, alias="RECOVERY_WINDOW_SECONDS")

    register_rate_limit: int = Field(default=5, gt=0, alias="REGISTER_RATE_LIMIT")
    register_rate_window_seconds: int = Field(
        default=3600, gt=0, alias="REGISTER_RATE_WINDOW_SECONDS"
    )
    login_ip_rate_limit: int = Field(default=10, gt=0, alias="LOGIN_IP_RATE_LIMIT")
    login_identity_rate_limit: int = Field(default=10, gt=0, alias="LOGIN_IDENTITY_RATE_LIMIT")
    login_rate_window_seconds: int = Field(default=60, gt=0, alias="LOGIN_RATE_WINDOW_SECONDS")
    query_rate_limit: int = Field(default=60, gt=0, alias="QUERY_RATE_LIMIT")
    query_rate_window_seconds: int = Field(default=60, gt=0, alias="QUERY_RATE_WINDOW_SECONDS")
    invitation_rate_limit: int = Field(default=10, gt=0, alias="INVITATION_RATE_LIMIT")
    invitation_rate_window_seconds: int = Field(
        default=3600, gt=0, alias="INVITATION_RATE_WINDOW_SECONDS"
    )

    r2_account_id: str = Field(default="", alias="R2_ACCOUNT_ID")
    r2_access_key_id: str = Field(default="", alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str = Field(default="", alias="R2_SECRET_ACCESS_KEY")
    r2_bucket_name: str = Field(default="", alias="R2_BUCKET_NAME")
    r2_endpoint_url: str = Field(default="", alias="R2_ENDPOINT_URL")
    document_upload_url_expires_seconds: int = Field(
        default=900,
        alias="DOCUMENT_UPLOAD_URL_EXPIRES_SECONDS",
    )

    jwt_secret_key: str = Field(
        default="change-me-in-production-use-32-bytes-min",
        alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    @model_validator(mode="after")
    def validate_pilot(self):
        from app.integrations.payments.stripe import test_secret

        key = self.stripe_secret_key.get_secret_value()
        if key and not test_secret(key):
            raise ValueError("Only a Stripe test secret key is accepted")
        if self.app_env not in {"pilot", "production"}:
            return self
        keys = [
            self.jwt_secret_key,
            self.invitation_secret_key,
            self.recovery_secret_key.get_secret_value(),
        ]
        if self.debug or any(len(key) < 32 or key.startswith("change-me") for key in keys):
            raise ValueError(
                "Pilot requires debug off and three non-default secrets of at least 32 characters"
            )
        if len(set(keys)) != len(keys):
            raise ValueError("Pilot secrets must be distinct")
        urls = [self.frontend_url, *self.backend_cors_origins]
        if not self.backend_cors_origins or any(
            urlsplit(url).scheme != "https"
            or not urlsplit(url).hostname
            or urlsplit(url).username
            or urlsplit(url).password
            or urlsplit(url).query
            or urlsplit(url).fragment
            for url in urls
        ):
            raise ValueError("Pilot requires explicit HTTPS frontend and CORS origins")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
