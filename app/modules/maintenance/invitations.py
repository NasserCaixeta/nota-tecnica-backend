import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.audit.service import append_audit
from app.modules.maintenance.models import InvitationIntent, ServiceInvitation
from app.modules.maintenance.revisions import current_revision, locked_record
from app.modules.maintenance.service import can_operate_record
from app.modules.users.models import ParticipationStatus
from app.modules.vehicles.models import GarageValidationStatus, VehicleUser, VerificationStatus


def invitation_token(nonce):
    secret = get_settings().invitation_secret_key
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="Service invitations are not configured")
    signature = hmac.new(secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    return f"{nonce}.{signature}"


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def aware(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def create_invitation(session, record_id, payload, actor):
    record = await locked_record(session, record_id)
    await can_operate_record(session, record, actor)
    if record.origin != "workshop" or record.superseded_by_id is not None:
        raise HTTPException(status_code=409, detail="Only workshop services can invite customers")
    if record.current_revision_id != payload.revision_id:
        raise HTTPException(status_code=409, detail="The service revision has changed")
    nonce = secrets.token_urlsafe(32)
    token = invitation_token(nonce)
    now = datetime.now(UTC)
    previous = (
        await session.scalars(
            select(ServiceInvitation).where(
                ServiceInvitation.record_id == record.id,
                ServiceInvitation.revoked_at.is_(None),
                ServiceInvitation.consumed_at.is_(None),
            )
        )
    ).all()
    for item in previous:
        item.revoked_at = now
    invitation = ServiceInvitation(
        record_id=record.id,
        revision_id=record.current_revision_id,
        recipient_email=str(payload.recipient_email).casefold(),
        nonce=nonce,
        token_hash=token_hash(token),
        created_at=now,
        expires_at=now + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()
    await append_audit(
        session,
        actor_id=actor.id,
        action="service_invitation.created",
        target_type="service_invitation",
        target_id=invitation.id,
        metadata={"record_id": record.id, "revision_id": record.current_revision_id},
    )
    await session.commit()
    return {
        "id": invitation.id,
        "created_at": invitation.created_at,
        "expires_at": invitation.expires_at,
        "token": token,
        "url": f"{get_settings().frontend_url.rstrip('/')}/convite-servico#{token}",
    }


async def resolve_invitation(session, token, actor):
    # Only the token hash is used for lookup; the nonce contains no business identifiers.
    invitation = await session.scalar(
        select(ServiceInvitation).where(ServiceInvitation.token_hash == token_hash(token))
    )
    if invitation is None or invitation.recipient_email != actor.email.casefold():
        raise HTTPException(status_code=404, detail="Invitation not found")
    record = await locked_record(session, invitation.record_id)
    invitation = await session.scalar(
        select(ServiceInvitation)
        .where(ServiceInvitation.id == invitation.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = datetime.now(UTC)
    if (
        invitation.revoked_at
        or invitation.consumed_at
        or aware(invitation.expires_at) <= now
        or invitation.revision_id != record.current_revision_id
        or record.superseded_by_id
    ):
        raise HTTPException(status_code=410, detail="Invitation is no longer available")
    if not hmac.compare_digest(invitation_token(invitation.nonce), token):
        raise HTTPException(status_code=404, detail="Invitation not found")
    return invitation, record


async def accept_invitation(session, token, actor):
    invitation, record = await resolve_invitation(session, token, actor)
    intent = await session.scalar(
        select(InvitationIntent).where(
            InvitationIntent.invitation_id == invitation.id, InvitationIntent.user_id == actor.id
        )
    )
    if intent is None:
        session.add(InvitationIntent(invitation_id=invitation.id, user_id=actor.id))
    if actor.participation_status != ParticipationStatus.APPROVED:
        await session.commit()
        return {"state": "participation_pending"}
    link = await session.scalar(
        select(VehicleUser).where(
            VehicleUser.user_id == actor.id, VehicleUser.vehicle_id == record.vehicle_id
        )
    )
    if (
        link is None
        or link.verification_status != VerificationStatus.VERIFIED
        or link.garage_status != GarageValidationStatus.ACTIVE
    ):
        await session.commit()
        return {"state": "relationship_required"}
    revision = await current_revision(session, record)
    if revision.customer_user_id not in (None, actor.id):
        raise HTTPException(status_code=409, detail="Service already assigned to another customer")
    revision.customer_user_id = actor.id
    revision.review_version += 1
    invitation.consumed_at = datetime.now(UTC)
    invitation.consumed_by_id = actor.id
    await append_audit(
        session,
        actor_id=actor.id,
        action="service_invitation.accepted",
        target_type="service_invitation",
        target_id=invitation.id,
        metadata={"record_id": record.id, "revision_id": revision.id},
    )
    await session.commit()
    return {"state": "awaiting_confirmation", "record_id": record.id, "revision_id": revision.id}


async def request_invitation_relationship(session, payload, actor):
    from app.modules.vehicles.models import Vehicle, VehicleRelationshipType, VehicleUser

    invitation, record = await resolve_invitation(session, payload.token, actor)
    vehicle = await session.get(Vehicle, record.vehicle_id)
    if payload.vehicle.plate != vehicle.plate:
        raise HTTPException(status_code=422, detail="Vehicle plate does not match the invitation")
    link = await session.scalar(
        select(VehicleUser).where(
            VehicleUser.user_id == actor.id, VehicleUser.vehicle_id == vehicle.id
        )
    )
    if link is None:
        link = VehicleUser(
            vehicle_id=vehicle.id,
            user_id=actor.id,
            relationship_type=payload.vehicle.relationship_type or VehicleRelationshipType.OWNER,
            relationship_note=payload.vehicle.relationship_note,
            declared_vehicle_data=payload.vehicle.model_dump(
                mode="json", exclude={"relationship_type", "relationship_note"}
            ),
            verification_status=VerificationStatus.PENDING,
            garage_status=GarageValidationStatus.PENDING_DOCUMENTS,
        )
        session.add(link)
        await session.flush()
        await append_audit(
            session,
            actor_id=actor.id,
            action="service_invitation.relationship",
            target_type="vehicle_link",
            target_id=link.id,
        )
    await session.commit()
    return {
        "vehicle_id": vehicle.id,
        "vehicle_link_id": link.id,
        "garage_status": link.garage_status,
    }
