from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.vehicles.router import router as vehicles_router
from app.modules.workshops.router import router as workshops_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(vehicles_router)
router.include_router(workshops_router)
