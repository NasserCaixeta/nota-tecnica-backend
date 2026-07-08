from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.integrations.storage.r2 import StorageClient, create_storage_client
from app.modules.auth.dependencies import get_current_user
from app.modules.documents.schemas import DocumentUploadIntentCreate, DocumentUploadIntentRead
from app.modules.documents.service import create_vehicle_link_document_upload_intent
from app.modules.garage.schemas import (
    GarageDashboard,
    GarageRelationshipUpdate,
    GarageReviewSubmitResponse,
    GarageVehicleCreate,
    GarageVehicleItem,
)
from app.modules.garage.service import (
    create_garage_vehicle,
    get_garage_dashboard,
    get_garage_vehicle,
    list_garage_vehicle_items,
    submit_garage_vehicle_review,
    update_garage_relationship,
)
from app.modules.users.models import User

router = APIRouter(prefix="/garage", tags=["garage"])


def get_storage_client() -> Callable[[], StorageClient]:
    return create_storage_client


@router.get("", response_model=GarageDashboard)
async def read_garage_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GarageDashboard:
    return await get_garage_dashboard(session, current_user)


@router.get("/vehicles", response_model=list[GarageVehicleItem])
async def read_garage_vehicles(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[GarageVehicleItem]:
    return await list_garage_vehicle_items(session, current_user)


@router.post("/vehicles", response_model=GarageVehicleItem, status_code=status.HTTP_201_CREATED)
async def create_vehicle_in_garage(
    payload: GarageVehicleCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GarageVehicleItem:
    return await create_garage_vehicle(session, payload, current_user)


@router.get("/vehicles/{vehicle_id}", response_model=GarageVehicleItem)
async def read_garage_vehicle(
    vehicle_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GarageVehicleItem:
    return await get_garage_vehicle(session, vehicle_id, current_user)


@router.patch("/vehicle-links/{vehicle_link_id}/relationship", response_model=GarageVehicleItem)
async def patch_garage_relationship(
    vehicle_link_id: int,
    payload: GarageRelationshipUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GarageVehicleItem:
    return await update_garage_relationship(session, vehicle_link_id, payload, current_user)


@router.post(
    "/vehicle-links/{vehicle_link_id}/submit-review",
    response_model=GarageReviewSubmitResponse,
)
async def submit_garage_review(
    vehicle_link_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GarageReviewSubmitResponse:
    return await submit_garage_vehicle_review(session, vehicle_link_id, current_user)


@router.post(
    "/vehicle-links/{vehicle_link_id}/resubmit-review",
    response_model=GarageReviewSubmitResponse,
)
async def resubmit_garage_review(
    vehicle_link_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GarageReviewSubmitResponse:
    return await submit_garage_vehicle_review(session, vehicle_link_id, current_user)


@router.post(
    "/vehicle-links/{vehicle_link_id}/documents/upload-intents",
    response_model=DocumentUploadIntentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_garage_document_upload_intent(
    vehicle_link_id: int,
    payload: DocumentUploadIntentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    storage_client_factory: Annotated[Callable[[], StorageClient], Depends(get_storage_client)],
) -> DocumentUploadIntentRead:
    return await create_vehicle_link_document_upload_intent(
        session,
        vehicle_link_id,
        payload,
        current_user,
        storage_client_factory(),
    )
