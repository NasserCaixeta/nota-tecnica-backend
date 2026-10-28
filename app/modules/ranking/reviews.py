from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.modules.audit.service import append_audit
from app.modules.maintenance.models import MaintenanceRecord
from app.modules.maintenance.publication import published_maintenance_select
from app.modules.maintenance.revisions import current_revision, locked_record
from app.modules.ranking.models import ServiceReview
from app.modules.workshops.models import WorkshopUser


class ServiceReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    revision_id: int = Field(ge=1)
    stars: int = Field(ge=1, le=5, strict=True)
    comment: str | None = Field(default=None, max_length=2000)
    expected_version: int | None = Field(default=None, ge=1)


class ServiceReviewModeration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    comment_hidden: bool
    reason: str = Field(min_length=1, max_length=2000)


def review_to_read(review):
    return {
        key: getattr(review, key)
        for key in (
            "id",
            "record_id",
            "revision_id",
            "stars",
            "comment",
            "comment_hidden",
            "review_version",
        )
    }


async def put_service_review(session, record_id, payload, actor):
    record = await locked_record(session, record_id)
    revision = await current_revision(session, record)
    if revision.id != payload.revision_id:
        raise HTTPException(status_code=409, detail="The service revision has changed")
    if revision.customer_user_id != actor.id:
        raise HTTPException(status_code=403, detail="Only the acknowledging customer can review")
    if record.workshop_id and await session.scalar(
        select(WorkshopUser.id).where(
            WorkshopUser.user_id == actor.id, WorkshopUser.workshop_id == record.workshop_id
        )
    ):
        raise HTTPException(
            status_code=403, detail="Workshop representatives cannot review their own workshop"
        )
    if (
        await session.scalar(
            published_maintenance_select().where(MaintenanceRecord.id == record.id)
        )
        is None
    ):
        raise HTTPException(status_code=409, detail="Only published services can be reviewed")
    review = await session.scalar(
        select(ServiceReview).where(
            ServiceReview.record_id == record.id, ServiceReview.customer_user_id == actor.id
        )
    )
    if review is None:
        review = ServiceReview(
            record_id=record.id,
            customer_user_id=actor.id,
            revision_id=revision.id,
            stars=payload.stars,
            comment=payload.comment,
        )
        session.add(review)
    else:
        if payload.expected_version is None or review.review_version != payload.expected_version:
            raise HTTPException(status_code=409, detail="The review has changed")
        review.revision_id = revision.id
        review.stars = payload.stars
        review.comment = payload.comment
        # Editing a rating cannot reverse a moderator's decision about its public text.
        review.review_version += 1
    await session.flush()
    await append_audit(
        session,
        actor_id=actor.id,
        action="service_review.saved",
        target_type="service_review",
        target_id=review.id,
        version=review.review_version,
    )
    await session.commit()
    return review_to_read(review)


async def moderate_service_review(session, review_id, payload, actor):
    original = await session.get(ServiceReview, review_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Review not found")
    await locked_record(session, original.record_id)
    review = await session.scalar(
        select(ServiceReview)
        .where(ServiceReview.id == review_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if review.review_version != payload.expected_version:
        raise HTTPException(status_code=409, detail="The review has changed")
    review.comment_hidden = payload.comment_hidden
    review.moderation_reason = payload.reason
    review.review_version += 1
    await append_audit(
        session,
        actor_id=actor.id,
        action="service_review.comment_moderated",
        target_type="service_review",
        target_id=review.id,
        version=review.review_version,
        reason=payload.reason,
    )
    await session.commit()
    return review_to_read(review)
