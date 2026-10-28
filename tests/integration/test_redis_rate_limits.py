import asyncio
import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.rate_limit import enforce_rate_limit


async def test_real_redis_atomic_threshold_reset_and_isolation(monkeypatch):
    url = os.environ.get("TEST_REDIS_URL")
    if not url:
        pytest.skip("TEST_REDIS_URL must identify local Redis database15")
    parsed = make_url(url)
    if parsed.host not in {"localhost", "127.0.0.1"} or parsed.database != "15":
        pytest.fail("Refusing rate-limit integration outside local Redis database15")
    monkeypatch.setenv("REDIS_URL", url)
    get_settings.cache_clear()
    scope = "integration-" + uuid4().hex

    async def attempt():
        try:
            await enforce_rate_limit(scope, "synthetic@example.invalid", 3, 1)
            return 200
        except HTTPException as exc:
            assert exc.status_code == 429 and int(exc.headers["Retry-After"]) > 0
            return 429

    try:
        outcomes = await asyncio.gather(*(attempt() for _ in range(10)))
        assert outcomes.count(200) == 3 and outcomes.count(429) == 7
        await enforce_rate_limit(scope, "different@example.invalid", 3, 1)
        await asyncio.sleep(1.1)
        assert await attempt() == 200
    finally:
        get_settings.cache_clear()
