import asyncio
from typing import TypedDict

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import get_async_session_factory

router = APIRouter(tags=["health"])


class HealthResponse(TypedDict):
    status: str
    app: str
    environment: str


def build_health_response() -> HealthResponse:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
    }


@router.get("/health")
def healthcheck() -> HealthResponse:
    return build_health_response()


async def check_dependencies():
    async with get_async_session_factory()() as session:
        await session.execute(text("SELECT 1"))
    client = Redis.from_url(get_settings().redis_url, socket_connect_timeout=2, socket_timeout=2)
    try:
        await client.ping()
    finally:
        await client.aclose()


@router.get("/ready")
async def readiness():
    try:
        await asyncio.wait_for(check_dependencies(), timeout=4)
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ready"}
