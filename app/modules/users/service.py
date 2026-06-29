from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.security import hash_password
from app.modules.users.models import User, UserProfileType
from app.modules.users.schemas import UserCreate


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, payload: UserCreate) -> User:
    if payload.profile_type == UserProfileType.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Public registration cannot create admin users",
        )

    if await get_user_by_email(session, str(payload.email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    cpf_result = await session.execute(select(User).where(User.cpf == payload.cpf))
    if cpf_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="CPF already registered",
        )

    user = User(
        full_name=payload.full_name,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        cpf=payload.cpf,
        phone=payload.phone,
        birth_date=payload.birth_date,
        profile_type=payload.profile_type,
        zip_code=payload.zip_code,
        street=payload.street,
        number=payload.number,
        neighborhood=payload.neighborhood,
        city=payload.city,
        state=payload.state,
        complement=payload.complement,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
