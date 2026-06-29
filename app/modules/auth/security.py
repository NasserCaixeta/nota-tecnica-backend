from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings, get_settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(subject: str, settings: Settings | None = None) -> str:
    resolved_settings = settings or get_settings()
    expires_at = datetime.now(UTC) + timedelta(
        minutes=resolved_settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expires_at}
    return jwt.encode(
        payload,
        resolved_settings.jwt_secret_key,
        algorithm=resolved_settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, object]:
    resolved_settings = settings or get_settings()
    return jwt.decode(
        token,
        resolved_settings.jwt_secret_key,
        algorithms=[resolved_settings.jwt_algorithm],
    )
