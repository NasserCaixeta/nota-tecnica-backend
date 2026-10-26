from dataclasses import replace

import pytest


@pytest.mark.parametrize(
    "changed,want",
    [
        (None, True),
        ("submitted", False),
        ("evidence_approved", False),
        ("admin_approved", False),
        ("customer_acknowledged", False),
        ("link_active", False),
        ("dispute_open", False),
    ],
)
def test_each_publication_requirement_is_indispensable(changed, want):
    from app.modules.maintenance.publication import PublicationFacts, is_publication_eligible

    facts = PublicationFacts(True, True, True, True, True, False)
    if changed:
        facts = replace(facts, **{changed: changed == "dispute_open"})
    assert is_publication_eligible(facts) is want
