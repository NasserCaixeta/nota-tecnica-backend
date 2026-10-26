import os

import pytest
import pytest_asyncio
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.fixture
def pg_url() -> str:
    value = os.environ.get("TEST_POSTGRES_URL")
    if not value:
        pytest.skip("TEST_POSTGRES_URL must name a disposable PostgreSQL test database")
    url = make_url(value)
    if url.host not in {"localhost", "127.0.0.1"} or not (url.database or "").endswith("_test"):
        pytest.fail("Refusing destructive tests outside a local database ending in _test")
    return value


@pytest_asyncio.fixture
async def pg_engine(pg_url):
    from sqlalchemy import text

    engine = create_async_engine(pg_url)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    yield engine
    await engine.dispose()
