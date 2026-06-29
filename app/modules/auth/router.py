from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.schemas import LoginRequest, TokenResponse
from app.modules.auth.service import authenticate_user, create_user_access_token
from app.modules.users.schemas import UserCreate, UserRead
from app.modules.users.service import create_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    return await create_user(session, payload)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    user = await authenticate_user(session, str(payload.email), payload.password)
    return TokenResponse(access_token=create_user_access_token(user))
