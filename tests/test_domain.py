"""Domain contract: closed sets, one routing matrix, complete results."""

import pytest

from nodeassistant.domain import Category, Owner, Priority, TriageResult, owner_for


def test_category_priority_and_owner_are_the_closed_sets():
    assert [item.value for item in Category] == [
        "Sales",
        "Support",
        "Billing",
        "Technical",
        "Other",
    ]
    assert [item.value for item in Priority] == ["Low", "Medium", "High", "Urgent"]
    assert [item.value for item in Owner] == [
        "Sales Team",
        "Client Success",
        "Finance",
        "Engineering",
    ]


def test_owner_for_maps_each_category_including_support():
    assert owner_for(Category.SALES) is Owner.SALES_TEAM
    assert owner_for(Category.SUPPORT) is Owner.CLIENT_SUCCESS
    assert owner_for(Category.BILLING) is Owner.FINANCE
    assert owner_for(Category.TECHNICAL) is Owner.ENGINEERING
    assert owner_for(Category.OTHER) is Owner.CLIENT_SUCCESS


def test_triage_result_keeps_a_complete_triage():
    result = TriageResult(
        summary="Portal is down for staff.",
        category=Category.TECHNICAL,
        priority=Priority.URGENT,
        reason="Production access outage blocking staff now.",
        owner=Owner.ENGINEERING,
        draft="Draft: we are looking at the portal outage.",
    )

    assert result.summary == "Portal is down for staff."
    assert result.category is Category.TECHNICAL
    assert result.priority is Priority.URGENT
    assert result.reason == "Production access outage blocking staff now."
    assert result.owner is Owner.ENGINEERING
    assert result.draft == "Draft: we are looking at the portal outage."


@pytest.mark.parametrize(
    "field",
    ["summary", "reason", "draft"],
)
def test_triage_result_rejects_a_missing_prose_field(field):
    payload = {
        "summary": "A summary.",
        "category": Category.SALES,
        "priority": Priority.MEDIUM,
        "reason": "A commercial lead.",
        "owner": Owner.SALES_TEAM,
        "draft": "Draft reply.",
    }
    payload[field] = "   "

    with pytest.raises(ValueError):
        TriageResult(**payload)


def test_triage_result_rejects_an_owner_outside_the_matrix():
    with pytest.raises(ValueError):
        TriageResult(
            summary="A sales conversation.",
            category=Category.SALES,
            priority=Priority.MEDIUM,
            reason="Commercial automation opportunity.",
            owner=Owner.ENGINEERING,
            draft="Draft reply.",
        )
