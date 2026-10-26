from dataclasses import dataclass

from sqlalchemy import exists, select

from app.modules.documents.models import Document, DocumentReviewStatus, DocumentType
from app.modules.maintenance.models import MaintenanceRecord, MaintenanceRevision
from app.modules.vehicles.models import GarageValidationStatus, VehicleUser, VerificationStatus

SERVICE_EVIDENCE_TYPES = (
    DocumentType.INVOICE,
    DocumentType.SERVICE_ORDER,
    DocumentType.PAYMENT_RECEIPT,
)


@dataclass(frozen=True)
class PublicationFacts:
    submitted: bool
    evidence_approved: bool
    admin_approved: bool
    customer_acknowledged: bool
    link_active: bool
    dispute_open: bool


def is_publication_eligible(facts: PublicationFacts) -> bool:
    return (
        all(
            (
                facts.submitted,
                facts.evidence_approved,
                facts.admin_approved,
                facts.customer_acknowledged,
                facts.link_active,
            )
        )
        and not facts.dispute_open
    )


def evidence_predicate(*, approved=True):
    clauses = [
        Document.maintenance_revision_id == MaintenanceRevision.id,
        Document.maintenance_record_id == MaintenanceRecord.id,
        Document.storage_verified.is_(True),
        Document.document_type.in_(SERVICE_EVIDENCE_TYPES),
    ]
    if approved:
        clauses.append(Document.review_status == DocumentReviewStatus.APPROVED)
    return exists(
        select(Document.id).where(*clauses).correlate(MaintenanceRevision, MaintenanceRecord)
    )


def published_maintenance_select():
    return (
        select(MaintenanceRecord)
        .join(
            MaintenanceRevision,
            (MaintenanceRevision.id == MaintenanceRecord.current_revision_id)
            & (MaintenanceRevision.record_id == MaintenanceRecord.id),
        )
        .where(
            MaintenanceRecord.superseded_by_id.is_(None),
            MaintenanceRecord.dispute_open.is_(False),
            MaintenanceRevision.editorial_status == "submitted",
            MaintenanceRevision.admin_status == "approved",
            MaintenanceRevision.customer_acknowledgement.in_(("author_acknowledged", "confirmed")),
            evidence_predicate(),
            exists(
                select(VehicleUser.id).where(
                    VehicleUser.user_id == MaintenanceRevision.customer_user_id,
                    VehicleUser.vehicle_id == MaintenanceRecord.vehicle_id,
                    VehicleUser.verification_status == VerificationStatus.VERIFIED,
                    VehicleUser.garage_status == GarageValidationStatus.ACTIVE,
                )
            ).correlate(MaintenanceRevision, MaintenanceRecord),
        )
    )
