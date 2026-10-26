from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.integrations.storage.r2 import StorageClient
from app.modules.auth.dependencies import get_approved_participant, get_current_user
from app.modules.documents.models import Document
from app.modules.documents.router import get_storage_client
from app.modules.documents.schemas import (
    DocumentRead,
    DocumentUploadIntentCreate,
    DocumentUploadIntentRead,
)
from app.modules.garage.schemas import GarageVehicleCreate
from app.modules.maintenance.acknowledgements import acknowledge_service, pending_customer_services
from app.modules.maintenance.disputes import (
    dispute_to_read,
    open_dispute,
    reply_dispute,
    require_dispute_reader,
    upload_dispute_evidence,
)
from app.modules.maintenance.duplicates import associate_service, duplicate_candidates
from app.modules.maintenance.invitations import (
    accept_invitation,
    create_invitation,
    invitation_token,
    request_invitation_relationship,
)
from app.modules.maintenance.models import (
    InvitationIntent,
    MaintenanceRevision,
    ServiceDispute,
    ServiceInvitation,
)
from app.modules.maintenance.moderation import submit_maintenance
from app.modules.maintenance.projections import PublishedMaintenanceRead
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
    ServiceDisputeCreate,
    ServiceDisputeMessageCreate,
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
        session,
        await create_maintenance_record(session, vehicle_id, payload, current_user),
        actor=current_user,
    )


@router.get(
    "/vehicles/{vehicle_id}/maintenance-records",
    response_model=list[MaintenanceRecordRead | PublishedMaintenanceRead],
)
async def read_vehicle_maintenance_records(
    vehicle_id: int,
    current_user: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MaintenanceRecordRead]:
    return [
        await record_to_read(session, record, actor=current_user)
        for record in await list_vehicle_maintenance_records(session, vehicle_id, current_user)
    ]


@router.get(
    "/maintenance-records/{record_id}",
    response_model=MaintenanceRecordRead | PublishedMaintenanceRead,
)
async def read_maintenance_record(
    record_id: int,
    current_user: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MaintenanceRecordRead:
    return await record_to_read(
        session, await get_maintenance_record(session, record_id, current_user), current_user
    )


@router.patch("/maintenance-records/{record_id}", response_model=MaintenanceRecordRead)
async def patch_maintenance_record(
    record_id: int,
    payload: MaintenanceRecordUpdate,
    current_user: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MaintenanceRecordRead:
    return await record_to_read(
        session,
        await update_maintenance_record(session, record_id, payload, current_user),
        actor=current_user,
    )


@router.post("/maintenance-records/{record_id}/submit", response_model=MaintenanceRecordRead)
async def post_submit_maintenance(
    record_id: int,
    payload: MaintenanceSubmit,
    current_user: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await record_to_read(
        session,
        await submit_maintenance(session, record_id, payload, current_user),
        actor=current_user,
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
        session,
        await create_workshop_maintenance(session, workshop_id, payload, current_user),
        actor=current_user,
    )


@router.get(
    "/workshops/{workshop_id}/maintenance-records",
    response_model=list[MaintenanceRecordRead | PublishedMaintenanceRead],
)
async def read_workshop_maintenance(
    workshop_id: int,
    current_user: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return [
        await record_to_read(session, record, actor=current_user)
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
        session,
        await acknowledge_service(session, record_id, payload.revision_id, actor),
        actor=actor,
    )


@router.get(
    "/customer-services/pending",
    response_model=list[MaintenanceRecordRead | PublishedMaintenanceRead],
)
async def read_pending_customer_services(
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return [
        await record_to_read(session, r, actor=actor)
        for r in await pending_customer_services(session, actor)
    ]


@router.post(
    "/maintenance-records/{record_id}/associate",
    response_model=MaintenanceRecordRead | PublishedMaintenanceRead,
)
async def post_service_association(
    record_id: int,
    payload: ServiceAssociation,
    response: Response,
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    record = await associate_service(session, record_id, payload, actor)
    response.status_code = 200 if actor.is_admin else 202
    return await record_to_read(session, record, actor=actor)


@router.post("/maintenance-records/{record_id}/disputes", status_code=201)
async def post_service_dispute(
    record_id: int,
    payload: ServiceDisputeCreate,
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await dispute_to_read(
        session, await open_dispute(session, record_id, payload, actor), actor
    )


@router.get("/maintenance-records/{record_id}/revisions")
async def read_service_revisions(
    record_id: int,
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    record = await get_maintenance_record(session, record_id, actor)
    # Historical private data is restricted to the involved actors and administrators.
    from app.modules.maintenance.revisions import current_revision
    from app.modules.maintenance.service import can_operate_record

    revision = await current_revision(session, record)
    if not actor.is_admin and revision.customer_user_id != actor.id:
        await can_operate_record(session, record, actor)
    revisions = (
        await session.scalars(
            select(MaintenanceRevision)
            .where(MaintenanceRevision.record_id == record_id)
            .order_by(MaintenanceRevision.revision_number)
        )
    ).all()
    return [
        {c.name: getattr(r, c.name) for c in MaintenanceRevision.__table__.columns}
        for r in revisions
    ]


@router.get("/maintenance-records/{record_id}/disputes")
async def read_record_disputes(
    record_id: int,
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    await get_maintenance_record(session, record_id, actor)
    disputes = (
        await session.scalars(select(ServiceDispute).where(ServiceDispute.record_id == record_id))
    ).all()
    return [
        await dispute_to_read(session, await require_dispute_reader(session, d.id, actor), actor)
        for d in disputes
    ]


@router.post("/service-disputes/{dispute_id}/messages")
async def post_dispute_reply(
    dispute_id: int,
    payload: ServiceDisputeMessageCreate,
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return await dispute_to_read(
        session, await reply_dispute(session, dispute_id, payload, actor), actor
    )


@router.post(
    "/service-disputes/{dispute_id}/documents/upload-intents",
    response_model=DocumentUploadIntentRead,
    status_code=201,
)
async def post_dispute_document(
    dispute_id: int,
    payload: DocumentUploadIntentCreate,
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[Callable[[], StorageClient], Depends(get_storage_client)],
):
    return await upload_dispute_evidence(session, dispute_id, payload, actor, storage())


@router.get("/maintenance-records/{record_id}/documents", response_model=list[DocumentRead])
async def read_service_documents(
    record_id: int,
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    record = await get_maintenance_record(session, record_id, actor)
    statement = select(Document).where(
        Document.maintenance_record_id == record.id,
        Document.maintenance_revision_id == record.current_revision_id,
    )
    if not actor.is_admin:
        statement = statement.where(Document.owner_user_id == actor.id)
    return list((await session.scalars(statement.order_by(Document.id))).all())


@router.get("/service-invitations/pending")
async def read_invitation_intents(
    actor: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    items = (
        await session.scalars(
            select(ServiceInvitation)
            .join(InvitationIntent)
            .where(
                InvitationIntent.user_id == actor.id,
                ServiceInvitation.consumed_at.is_(None),
                ServiceInvitation.revoked_at.is_(None),
            )
            .order_by(ServiceInvitation.id)
        )
    ).all()
    return [{"id": i.id, "created_at": i.created_at, "expires_at": i.expires_at} for i in items]


@router.post("/service-invitations/{invitation_id}/resume")
async def post_resume_invitation(
    invitation_id: int,
    actor: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    item = await session.scalar(
        select(ServiceInvitation)
        .join(InvitationIntent)
        .where(InvitationIntent.user_id == actor.id, ServiceInvitation.id == invitation_id)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return await accept_invitation(session, invitation_token(item.nonce), actor)


@router.get(
    "/maintenance-records/{record_id}/duplicates",
    response_model=list[MaintenanceRecordRead | PublishedMaintenanceRead],
)
async def read_duplicate_candidates(
    record_id: int,
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    return [
        await record_to_read(session, r, actor=actor)
        for r in await duplicate_candidates(session, record_id, actor)
    ]


@router.post("/service-invitations/{invitation_id}/relationship", status_code=201)
async def post_intent_relationship(
    invitation_id: int,
    payload: GarageVehicleCreate,
    actor: Annotated[User, Depends(get_approved_participant)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    item = await session.scalar(
        select(ServiceInvitation)
        .join(InvitationIntent)
        .where(InvitationIntent.user_id == actor.id, ServiceInvitation.id == invitation_id)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return await request_invitation_relationship(
        session, InvitationRelationship(token=invitation_token(item.nonce), vehicle=payload), actor
    )
