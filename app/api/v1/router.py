from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.modules.admin.router import router as admin_router
from app.modules.auth.router import router as auth_router
from app.modules.documents.router import router as documents_router
from app.modules.garage.router import router as garage_router
from app.modules.maintenance.router import router as maintenance_router
from app.modules.public.router import router as public_router
from app.modules.ranking.router import router as ranking_router
from app.modules.users.router import router as users_router
from app.modules.vehicles.router import router as vehicles_router
from app.modules.workshops.router import router as workshops_router

router = APIRouter()
router.include_router(health_router)
router.include_router(admin_router)
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(vehicles_router)
router.include_router(workshops_router)
router.include_router(maintenance_router)
router.include_router(documents_router)
router.include_router(garage_router)
router.include_router(public_router)
router.include_router(ranking_router)
