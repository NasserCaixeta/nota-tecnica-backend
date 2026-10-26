from fastapi import HTTPException

from app.modules.audit.service import append_audit
from app.modules.maintenance.models import ServiceDuplicateProposal
from app.modules.maintenance.revisions import create_revision, locked_record
from app.modules.maintenance.service import get_maintenance_record


async def associate_service(session, record_id, payload, actor):
    if record_id == payload.other_record_id:
        raise HTTPException(status_code=422, detail="Choose two distinct services")
    # Read permissions are enforced before either participant can suggest a match.
    await get_maintenance_record(session, record_id, actor)
    await get_maintenance_record(session, payload.other_record_id, actor)
    records = {
        rid: await locked_record(session, rid)
        for rid in sorted((record_id, payload.other_record_id))
    }
    first, second = records[record_id], records[payload.other_record_id]
    if first.vehicle_id != second.vehicle_id:
        raise HTTPException(status_code=422, detail="Services must refer to the same vehicle")
    if (
        first.current_revision_id != payload.revision_id
        or second.current_revision_id != payload.other_revision_id
        or first.superseded_by_id
        or second.superseded_by_id
    ):
        raise HTTPException(status_code=409, detail="The services have changed")
    proposal = ServiceDuplicateProposal(
        record_id=first.id,
        other_record_id=second.id,
        revision_id=payload.revision_id,
        other_revision_id=payload.other_revision_id,
        proposed_by_id=actor.id,
        reason=payload.reason,
        status="resolved" if actor.is_admin else "pending",
    )
    session.add(proposal)
    await session.flush()
    if actor.is_admin:
        second.superseded_by_id = first.id
        revision = await create_revision(session, first, actor_id=actor.id)
        # Consolidation never lets an administrator acknowledge data on the customer's behalf.
        revision.customer_acknowledgement = "awaiting_customer"
    await append_audit(
        session,
        actor_id=actor.id,
        action="maintenance.associated" if actor.is_admin else "maintenance.association_requested",
        target_type="service_duplicate_proposal",
        target_id=proposal.id,
        reason=payload.reason,
        metadata={"record_id": first.id, "other_record_id": second.id},
    )
    await session.commit()
    return first
