from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import get_approved_participant, get_current_user
from app.modules.maintenance.acknowledgements import acknowledge_service, pending_customer_services
from app.modules.maintenance.duplicates import associate_service
from app.modules.maintenance.invitations import (
    accept_invitation,
    create_invitation,
    request_invitation_relationship,
)
from app.modules.maintenance.moderation import submit_maintenance
from app.modules.maintenance.revisions import record_to_read
from app.modules.maintenance.schemas import (
    InvitationAccept,
    InvitationCreate,
    InvitationRelationship,
    MaintenanceRecordCreate,
    MaintenanceRecordRead,
    MaintenanceRecordUpdate,
    MaintenanceSubmit,
    ServiceAssociation,
    WorkshopMaintenanceCreate,
)
from app.modules.maintenance.service import (
    create_maintenance_record,
    create_workshop_maintenance,
    get_maintenance_record,
    list_vehicle_maintenance_records,
    list_workshop_maintenance,
    update_maintenance_record,
)
from app.modules.users.models import User

router = APIRouter(tags=["maintenance"])


@router.post(
    "/vehicles/{vehicle_id}/maintenance-records",
    response_model=MaintenanceRecordRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_vehicle_maintenance_record(
    vehicle_id: int,
    payload: MaintenanceRecordCreate,
    current_user: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MaintenanceRecordRead:
    return await record_to_read(
        session, await create_maintenance_record(session, vehicle_id, payload, current_user)
    )


@router.get(
    "/vehicles/{vehicle_id}/maintenance-records",
    response_model=list[MaintenanceRecordRead],
)
async def read_vehicle_maintenance_records(
    vehicle_id: int,
    current_user: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MaintenanceRecordRead]:
    return [
        await record_to_read(session, record)
        for record in await list_vehicle_maintenance_records(session, vehicle_id, current_user)
    ]


@router.get("/maintenance-records/{record_id}", response_model=MaintenanceRecordRead)
async def read_maintenance_record(
    record_id: int,
    current_user: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MaintenanceRecordRead:
    return await record_to_read(
        session, await get_maintenance_record(session, record_id, current_user)
    )


@router.patch("/maintenance-records/{record_id}", response_model=MaintenanceRecordRead)
async def patch_maintenance_record(
    record_id: int,
    payload: MaintenanceRecordUpdate,
    current_user: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MaintenanceRecordRead:
    return await record_to_read(
        session, await update_maintenance_record(session, record_id, payload, current_user)
    )


@router.post("/maintenance-records/{record_id}/submit", response_model=MaintenanceRecordRead)
async def post_submit_maintenance(
    record_id: int,
    payload: MaintenanceSubmit,
    current_user: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await record_to_read(
        session, await submit_maintenance(session, record_id, payload, current_user)
    )


@router.post(
    "/workshops/{workshop_id}/maintenance-records",
    response_model=MaintenanceRecordRead,
    status_code=201,
)
async def post_workshop_maintenance(
    workshop_id: int,
    payload: WorkshopMaintenanceCreate,
    current_user: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await record_to_read(
        session, await create_workshop_maintenance(session, workshop_id, payload, current_user)
    )


@router.get(
    "/workshops/{workshop_id}/maintenance-records", response_model=list[MaintenanceRecordRead]
)
async def read_workshop_maintenance(
    workshop_id: int,
    current_user: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return [
        await record_to_read(session, record)
        for record in await list_workshop_maintenance(session, workshop_id, current_user)
    ]


@router.post("/maintenance-records/{record_id}/invitations", status_code=201)
async def post_service_invitation(
    record_id: int,
    payload: InvitationCreate,
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await create_invitation(session, record_id, payload, actor)


@router.post("/service-invitations/accept")
async def post_accept_invitation(
    payload: InvitationAccept,
    actor: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await accept_invitation(session, payload.token, actor)


@router.post("/service-invitations/relationship", status_code=201)
async def post_invitation_relationship(
    payload: InvitationRelationship,
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await request_invitation_relationship(session, payload, actor)


@router.post("/maintenance-records/{record_id}/acknowledge", response_model=MaintenanceRecordRead)
async def post_service_acknowledgement(
    record_id: int,
    payload: MaintenanceSubmit,
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await record_to_read(
        session, await acknowledge_service(session, record_id, payload.revision_id, actor)
    )


@router.get("/customer-services/pending", response_model=list[MaintenanceRecordRead])
async def read_pending_customer_services(
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return [
        await record_to_read(session, r) for r in await pending_customer_services(session, actor)
    ]


@router.post("/maintenance-records/{record_id}/associate", response_model=MaintenanceRecordRead)
async def post_service_association(
    record_id: int,
    payload: ServiceAssociation,
    response: Response,
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    record = await associate_service(session, record_id, payload, actor)
    response.status_code = 200 if actor.is_admin else 202
    return await record_to_read(session, record)
