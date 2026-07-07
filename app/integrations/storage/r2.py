from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.client import BaseClient
from botocore.config import Config

from app.core.config import Settings, get_settings
from app.core.validators import normalize_plate


class R2ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class R2Config:
    account_id: str
    access_key_id: str
    secret_access_key: str = field(repr=False)
    bucket_name: str
    endpoint_url: str


@dataclass(frozen=True)
class PresignedUpload:
    upload_url: str
    required_headers: dict[str, str]


class StorageClient:
    def __init__(self, config: R2Config, client: BaseClient | None = None) -> None:
        self.config = config
        self._client = client or boto3.client(
            "s3",
            endpoint_url=s3_endpoint_url(config),
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    def create_presigned_upload_url(
        self,
        storage_key: str,
        content_type: str,
        expires_seconds: int,
    ) -> PresignedUpload:
        upload_url = self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.config.bucket_name,
                "Key": storage_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_seconds,
        )
        return PresignedUpload(
            upload_url=upload_url,
            required_headers={"Content-Type": content_type},
        )


def create_r2_config(settings: Settings | None = None) -> R2Config:
    resolved_settings = settings or get_settings()
    return R2Config(
        account_id=resolved_settings.r2_account_id,
        access_key_id=resolved_settings.r2_access_key_id,
        secret_access_key=resolved_settings.r2_secret_access_key,
        bucket_name=resolved_settings.r2_bucket_name,
        endpoint_url=resolved_settings.r2_endpoint_url,
    )


def validate_r2_config(config: R2Config) -> None:
    if not all(
        [
            config.account_id,
            config.access_key_id,
            config.secret_access_key,
            config.bucket_name,
            config.endpoint_url,
        ]
    ):
        raise R2ConfigurationError("R2 configuration is incomplete")


def s3_endpoint_url(config: R2Config) -> str:
    endpoint_url = config.endpoint_url.rstrip("/")
    bucket_suffix = f"/{config.bucket_name}"
    if endpoint_url.endswith(bucket_suffix):
        return endpoint_url[: -len(bucket_suffix)]
    return endpoint_url


def create_storage_client(settings: Settings | None = None) -> StorageClient:
    config = create_r2_config(settings)
    validate_r2_config(config)
    return StorageClient(config)


def safe_file_name(file_name: str) -> str:
    stem = Path(file_name).stem.lower()
    suffix = Path(file_name).suffix.lower()
    safe_stem = "".join(character if character.isalnum() else "-" for character in stem)
    safe_stem = "-".join(part for part in safe_stem.split("-") if part)
    return f"{safe_stem or 'document'}{suffix}"


def build_document_storage_key(plate: str, file_name: str) -> str:
    normalized_plate = normalize_plate(plate)
    return f"vehicles/{normalized_plate}/documents/{uuid4()}-{safe_file_name(file_name)}"
