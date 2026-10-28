import hashlib
import hmac
from typing import Annotated, Protocol

from fastapi import Depends, HTTPException, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

COUNTER_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {count, redis.call('TTL', KEYS[1])}
"""


class RateLimitUnavailable(RuntimeError):
    pass


class RateLimitBackend(Protocol):
    async def increment(self, key: str, window_seconds: int) -> tuple[int, int]: ...


class RedisRateLimitBackend:
    async def increment(self, key: str, window_seconds: int) -> tuple[int, int]:
        client = Redis.from_url(
            get_settings().redis_url, socket_connect_timeout=2, socket_timeout=2
        )
        try:
            count, ttl = await client.eval(COUNTER_SCRIPT, 1, key, window_seconds)
            return int(count), max(1, int(ttl))
        except (RedisError, OSError, ValueError, TypeError):
            raise RateLimitUnavailable() from None
        finally:
            await client.aclose()


def get_rate_limit_backend() -> RateLimitBackend:
    return RedisRateLimitBackend()


async def enforce_rate_limit(
    scope: str,
    identity: str,
    limit: int,
    window_seconds: int,
    *,
    backend: RateLimitBackend | None = None,
):
    digest = hmac.new(
        get_settings().jwt_secret_key.encode(), identity.strip().casefold().encode(), hashlib.sha256
    ).hexdigest()
    key = f"nt:rate:{scope}:{digest}"
    try:
        count, ttl = await (backend or get_rate_limit_backend()).increment(key, window_seconds)
    except RateLimitUnavailable:
        raise HTTPException(
            503,
            "Proteção de tentativas temporariamente indisponível. Tente novamente.",
            headers={"Retry-After": "10"},
        ) from None
    if count > limit:
        raise HTTPException(
            429,
            "Limite de tentativas atingido. Tente novamente mais tarde.",
            headers={"Retry-After": str(max(1, ttl))},
        )


async def enforce_query_budget(
    request: Request, backend: Annotated[RateLimitBackend, Depends(get_rate_limit_backend)]
):
    settings = get_settings()
    await enforce_rate_limit(
        "query-ip",
        request.client.host if request.client else "unknown",
        settings.query_rate_limit,
        settings.query_rate_window_seconds,
        backend=backend,
    )


async def enforce_registration_budget(
    request: Request, backend: Annotated[RateLimitBackend, Depends(get_rate_limit_backend)]
):
    settings = get_settings()
    await enforce_rate_limit(
        "register-ip",
        request.client.host if request.client else "unknown",
        settings.register_rate_limit,
        settings.register_rate_window_seconds,
        backend=backend,
    )
