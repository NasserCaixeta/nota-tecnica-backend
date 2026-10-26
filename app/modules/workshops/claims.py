from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.service import append_audit
from app.modules.documents.models import Document, DocumentReviewStatus, ValidationDocumentType
from app.modules.users.models import User
from app.modules.vehicles.models import VerificationStatus
from app.modules.workshops.models import Workshop, WorkshopClaim, WorkshopUser, WorkshopUserRole
from app.modules.workshops.schemas import WorkshopClaimRead

CLAIM_DOCUMENT_TYPES = {
    ValidationDocumentType.COMPANY_CONTRACT_OR_POWER_OF_ATTORNEY,
    ValidationDocumentType.REPRESENTATIVE_IDENTITY,
}


async def latest_claim_documents(session, claim_id):
    documents = (
        await session.scalars(
            select(Document)
            .where(Document.workshop_claim_id == claim_id)
            .order_by(Document.id.desc())
        )
    ).all()
    latest = {}
    for document in documents:
        latest.setdefault(document.validation_document_type, document)
    return list(latest.values())


async def claim_to_read(session, claim):
    office = await session.get(Workshop, claim.workshop_id)
    user = await session.get(User, claim.user_id)
    return WorkshopClaimRead(
        id=claim.id,
        workshop_id=office.id,
        user_id=user.id,
        user_full_name=user.full_name,
        trade_name=office.trade_name,
        cnpj=office.cnpj,
        status=claim.status,
        review_version=claim.review_version,
        reason=claim.reason,
        documents=await latest_claim_documents(session, claim.id),
    )


async def create_workshop_claim(session, workshop_id, user, *, commit=True):
    office = await session.get(Workshop, workshop_id)
    if office is None:
        raise HTTPException(status_code=404, detail="Workshop not found")
    existing = await session.scalar(
        select(WorkshopClaim).where(
            WorkshopClaim.workshop_id == workshop_id,
            WorkshopClaim.user_id == user.id,
        )
    )
    if existing is not None:
        if existing.status != VerificationStatus.REJECTED:
            raise HTTPException(status_code=409, detail="A representation request already exists")
        existing.status = VerificationStatus.PENDING
        existing.review_version += 1
        existing.reason = None
        claim = existing
    else:
        claim = WorkshopClaim(workshop_id=workshop_id, user_id=user.id)
        session.add(claim)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="A representation request already exists"
        ) from exc
    await append_audit(
        session,
        actor_id=user.id,
        action="workshop_claim.request",
        target_type="workshop_claim",
        target_id=claim.id,
        version=claim.review_version,
    )
    if commit:
        await session.commit()
    return claim


async def require_workshop_responsibility(
    session: AsyncSession,
    user_id: int,
    workshop_id: int,
) -> WorkshopUser:
    member = await session.scalar(
        select(WorkshopUser)
        .join(Workshop)
        .where(
            WorkshopUser.user_id == user_id,
            WorkshopUser.workshop_id == workshop_id,
            WorkshopUser.verification_status == VerificationStatus.VERIFIED,
            Workshop.verification_status == VerificationStatus.VERIFIED,
        )
    )
    if member is None:
        raise HTTPException(status_code=403, detail="Approved workshop representation is required")
    return member


async def review_workshop_claim(session, claim_id, payload, actor):
    claim = await session.scalar(
        select(WorkshopClaim)
        .where(WorkshopClaim.id == claim_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if claim is None:
        raise HTTPException(status_code=404, detail="Representation request not found")
    if claim.user_id == actor.id:
        raise HTTPException(
            status_code=409, detail="Administrators cannot approve their own workshop"
        )
    if claim.review_version != payload.expected_version:
        raise HTTPException(status_code=409, detail="The representation review has changed")
    if payload.decision not in {VerificationStatus.VERIFIED, VerificationStatus.REJECTED}:
        raise HTTPException(status_code=422, detail="Choose verified or rejected")
    if payload.decision == VerificationStatus.VERIFIED:
        documents = await latest_claim_documents(session, claim.id)
        approved = {
            document.validation_document_type
            for document in documents
            if document.storage_verified and document.review_status == DocumentReviewStatus.APPROVED
        }
        if not CLAIM_DOCUMENT_TYPES.issubset(approved):
            raise HTTPException(status_code=409, detail="Representation documents must be approved")
        office = await session.get(Workshop, claim.workshop_id)
        office.verification_status = VerificationStatus.VERIFIED
        member = await session.scalar(
            select(WorkshopUser).where(
                WorkshopUser.user_id == claim.user_id,
                WorkshopUser.workshop_id == claim.workshop_id,
            )
        )
        if member is None:
            member = WorkshopUser(
                workshop_id=claim.workshop_id, user_id=claim.user_id, role=WorkshopUserRole.OWNER
            )
            session.add(member)
        member.verification_status = VerificationStatus.VERIFIED
    else:
        member = await session.scalar(
            select(WorkshopUser).where(
                WorkshopUser.user_id == claim.user_id,
                WorkshopUser.workshop_id == claim.workshop_id,
            )
        )
        if member is not None:
            member.verification_status = VerificationStatus.REJECTED
    claim.status = payload.decision
    claim.reason = payload.reason
    claim.review_version += 1
    await append_audit(
        session,
        actor_id=actor.id,
        action="workshop_claim.review",
        target_type="workshop_claim",
        target_id=claim.id,
        version=claim.review_version,
        reason=payload.reason,
        metadata={"decision": payload.decision.value},
    )
    await session.commit()
    return await claim_to_read(session, claim)
