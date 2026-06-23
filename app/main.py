from fastapi import FastAPI

from app.api.router import router as root_router
from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    application = FastAPI(title=settings.app_name, debug=settings.debug)
    register_exception_handlers(application)
    application.include_router(root_router)
    application.include_router(v1_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()
