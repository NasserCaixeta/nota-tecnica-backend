from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.rate_limit import RateLimitBackend, enforce_rate_limit, get_rate_limit_backend
from app.db.session import get_db
from app.modules.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.modules.auth.service import authenticate_user, create_user_access_token
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import create_user, user_to_read

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    user = await create_user(session, payload)
    return await user_to_read(session, user)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    user = await authenticate_user(session, str(payload.email), payload.password)
    return TokenResponse(access_token=create_user_access_token(user))


@router.post("/forgot-password", status_code=202)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    backend: Annotated[RateLimitBackend, Depends(get_rate_limit_backend)],
):
    from app.modules.auth.recovery import NEUTRAL_MESSAGE, request_recovery

    settings = get_settings()
    await enforce_rate_limit(
        "recovery-ip",
        request.client.host if request.client else "unknown",
        settings.recovery_ip_limit,
        settings.recovery_window_seconds,
        backend=backend,
    )
    await enforce_rate_limit(
        "recovery-identity",
        str(payload.email),
        settings.recovery_identity_limit,
        settings.recovery_window_seconds,
        backend=backend,
    )
    await request_recovery(session, str(payload.email))
    return {"message": NEUTRAL_MESSAGE}


@router.post("/reset-password")
async def reset_account_password(
    payload: ResetPasswordRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    backend: Annotated[RateLimitBackend, Depends(get_rate_limit_backend)],
):
    from app.modules.auth.recovery import reset_password

    settings = get_settings()
    await enforce_rate_limit(
        "reset-ip",
        request.client.host if request.client else "unknown",
        settings.recovery_ip_limit,
        settings.recovery_window_seconds,
        backend=backend,
    )
    await reset_password(session, payload.token, payload.new_password.get_secret_value())
    return {"message": "Senha alterada. Entre novamente com a nova senha."}
