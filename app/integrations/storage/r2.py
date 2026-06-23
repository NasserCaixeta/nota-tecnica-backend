from dataclasses import dataclass, field

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class R2Config:
    account_id: str
    access_key_id: str
    secret_access_key: str = field(repr=False)
    bucket_name: str
    endpoint_url: str


def create_r2_config(settings: Settings | None = None) -> R2Config:
    resolved_settings = settings or get_settings()
    return R2Config(
        account_id=resolved_settings.r2_account_id,
        access_key_id=resolved_settings.r2_access_key_id,
        secret_access_key=resolved_settings.r2_secret_access_key,
        bucket_name=resolved_settings.r2_bucket_name,
        endpoint_url=resolved_settings.r2_endpoint_url,
    )
