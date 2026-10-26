from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ServiceReview(Base):
    __tablename__ = "service_reviews"
    __table_args__ = (
        UniqueConstraint("record_id", "customer_user_id", name="uq_service_review_customer"),
        CheckConstraint("stars >= 1 AND stars <= 5", name="ck_review_stars"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("maintenance_records.id"), index=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("maintenance_revisions.id"))
    customer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    stars: Mapped[int] = mapped_column()
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment_hidden: Mapped[bool] = mapped_column(default=False)
    moderation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
