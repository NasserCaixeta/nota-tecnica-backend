import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette import status

from app.integrations.storage.r2 import R2ConfigurationError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(R2ConfigurationError)
    async def unavailable_document_storage(_request: Request, _exc: R2ConfigurationError):
        return JSONResponse(
            status_code=503, content={"detail": "Document storage is not configured"}
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unexpected application error", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
