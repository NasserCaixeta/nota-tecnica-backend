from typing import TypedDict

from fastapi import APIRouter

from app.core.config import get_settings

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
