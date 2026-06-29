from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="Nota Tecnica API", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    debug: bool = Field(default=True, alias="DEBUG")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")

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

    r2_account_id: str = Field(default="", alias="R2_ACCOUNT_ID")
    r2_access_key_id: str = Field(default="", alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str = Field(default="", alias="R2_SECRET_ACCESS_KEY")
    r2_bucket_name: str = Field(default="", alias="R2_BUCKET_NAME")
    r2_endpoint_url: str = Field(default="", alias="R2_ENDPOINT_URL")

    jwt_secret_key: str = Field(
        default="change-me-in-production-use-32-bytes-min",
        alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")


@lru_cache
def get_settings() -> Settings:
    return Settings()
