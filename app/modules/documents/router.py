from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.integrations.storage.r2 import StorageClient, create_storage_client
from app.modules.auth.dependencies import get_current_user
from app.modules.documents.schemas import (
    DocumentCreate,
    DocumentRead,
    DocumentUploadConfirm,
    DocumentUploadIntentCreate,
    DocumentUploadIntentRead,
)
from app.modules.documents.service import (
    confirm_document_upload,
    create_document,
    create_document_upload_intent,
    get_document,
    list_vehicle_documents,
)
from app.modules.users.models import User

router = APIRouter(tags=["documents"])


def get_storage_client() -> Callable[[], StorageClient]:
    return create_storage_client


@router.post(
    "/vehicles/{vehicle_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_vehicle_document(
    vehicle_id: int,
    payload: DocumentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentRead:
    return await create_document(session, vehicle_id, payload, current_user)


@router.post(
    "/vehicles/{vehicle_id}/documents/upload-intents",
    response_model=DocumentUploadIntentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_vehicle_document_upload_intent(
    vehicle_id: int,
    payload: DocumentUploadIntentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    storage_client_factory: Annotated[Callable[[], StorageClient], Depends(get_storage_client)],
) -> DocumentUploadIntentRead:
    return await create_document_upload_intent(
        session,
        vehicle_id,
        payload,
        current_user,
        storage_client_factory(),
    )


@router.get("/vehicles/{vehicle_id}/documents", response_model=list[DocumentRead])
async def read_vehicle_documents(
    vehicle_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[DocumentRead]:
    return await list_vehicle_documents(session, vehicle_id, current_user)


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def read_document(
    document_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentRead:
    return await get_document(session, document_id, current_user)


@router.post("/documents/{document_id}/confirm-upload", response_model=DocumentRead)
async def confirm_uploaded_document(
    document_id: int,
    payload: DocumentUploadConfirm,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentRead:
    return await confirm_document_upload(session, document_id, payload, current_user)
