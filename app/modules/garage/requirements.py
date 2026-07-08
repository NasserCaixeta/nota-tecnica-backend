from app.modules.documents.models import ValidationDocumentType
from app.modules.vehicles.models import VehicleRelationshipType

REQUIRED_DOCUMENTS_BY_RELATIONSHIP: dict[
    VehicleRelationshipType,
    list[ValidationDocumentType],
] = {
    VehicleRelationshipType.OWNER: [ValidationDocumentType.CRLV],
    VehicleRelationshipType.SPOUSE: [
        ValidationDocumentType.CRLV,
        ValidationDocumentType.OWNER_AUTHORIZATION,
        ValidationDocumentType.RELATIONSHIP_PROOF,
    ],
    VehicleRelationshipType.FAMILY: [
        ValidationDocumentType.CRLV,
        ValidationDocumentType.OWNER_AUTHORIZATION,
        ValidationDocumentType.RELATIONSHIP_PROOF,
    ],
    VehicleRelationshipType.COMPANY_REPRESENTATIVE: [
        ValidationDocumentType.CRLV,
        ValidationDocumentType.COMPANY_CONTRACT_OR_POWER_OF_ATTORNEY,
        ValidationDocumentType.REPRESENTATIVE_IDENTITY,
    ],
    VehicleRelationshipType.FLEET_RESPONSIBLE: [
        ValidationDocumentType.CRLV,
        ValidationDocumentType.FLEET_AUTHORIZATION,
        ValidationDocumentType.REPRESENTATIVE_IDENTITY,
    ],
    VehicleRelationshipType.RECENT_BUYER: [
        ValidationDocumentType.CRLV,
        ValidationDocumentType.PURCHASE_RECEIPT_OR_ATPV,
    ],
    VehicleRelationshipType.AUTHORIZED_DRIVER: [
        ValidationDocumentType.CRLV,
        ValidationDocumentType.OWNER_AUTHORIZATION,
        ValidationDocumentType.DRIVER_IDENTITY,
    ],
    VehicleRelationshipType.OTHER: [
        ValidationDocumentType.CRLV,
        ValidationDocumentType.OWNER_AUTHORIZATION,
    ],
}


def required_documents_for_relationship(
    relationship_type: VehicleRelationshipType,
) -> list[ValidationDocumentType]:
    return REQUIRED_DOCUMENTS_BY_RELATIONSHIP[relationship_type]
