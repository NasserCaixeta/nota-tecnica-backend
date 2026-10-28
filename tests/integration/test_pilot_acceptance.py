"""Acceptance index: reuse business regressions rather than duplicate nineteen tests."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {
    "A01": ("test_participation_admin.py", "pending_account_cannot_operate"),
    "A02": ("test_workshop_claims.py", "one_account_can_be_customer"),
    "A03": ("integration/test_maintenance_concurrency.py", "two_service_reviewers"),
    "A04": ("test_garage_subscription.py", "five_total_slots"),
    "A05": ("test_vehicle_access.py", "declaring_existing_plate"),
    "A06": ("test_vehicle_access.py", "validated_additional_vehicle"),
    "A07": ("test_maintenance_moderation.py", "submission_requires_verified_evidence"),
    "A08": ("test_maintenance_moderation.py", "customer_service_publishes_only"),
    "A09": ("test_service_invitations.py", "invitation_is_seven_days"),
    "A10": ("test_service_duplicates.py", "two_origins_consolidate"),
    "A11": ("test_service_disputes.py", "dispute_after_confirmation"),
    "A12": ("test_service_disputes.py", "relevant_correction_preserves"),
    "A13": ("test_paid_history_access.py", "bought_history_is_sanitized"),
    "A14": ("test_payment_benefits.py", "duplicate_confirmations_grant_exact"),
    "A15": ("test_paid_history_access.py", "paid_history_exact_expiry"),
    "A16": ("integration/test_payment_concurrency.py", "simultaneous_payment_confirmations"),
    "A17": ("test_garage_subscription.py", "additional_vehicle_can_acknowledge"),
    "A18": ("test_service_reviews.py", "workshop_responsible_cannot_review"),
    "A19": ("test_ranking.py", "ranking_filters_by_category"),
}


def acceptance_index():
    result = {}
    for criterion, (file, fragment) in SCENARIOS.items():
        module = ast.parse((ROOT / file).read_text())
        names = [
            node.name
            for node in module.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and fragment in node.name
        ]
        assert len(names) == 1, (criterion, file, fragment, names)
        result[criterion] = f"tests/{file}::{names[0]}"
    return result


def test_acceptance_catalog_references_real_business_tests():
    # This validates the index, not a second execution of the business scenarios.
    assert len(acceptance_index()) == 19


if __name__ == "__main__":
    for criterion, node in acceptance_index().items():
        print(criterion, node)
    print("A20 frontend: npm run test:e2e (both repositories and local services required)")
