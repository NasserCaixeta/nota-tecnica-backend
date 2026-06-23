from fastapi import APIRouter

from app.api.v1.health import healthcheck

router = APIRouter()
router.add_api_route("/health", healthcheck, methods=["GET"], tags=["health"])
