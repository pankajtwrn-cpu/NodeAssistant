"""Triage use case with an injected model port. No network."""

from types import SimpleNamespace

import pytest

from nodeassistant.domain import Category, Owner, Priority, owner_for
from nodeassistant.triage import Triage, TriageFailure


class RecordingPort:
    def __init__(self, payload):
        self.payload = payload
        self.calls: list[str] = []

    def complete(self, request_text: str):
        self.calls.append(request_text)
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def _payload(**overrides):
    fields = {
        "summary": "A short summary.",
        "category": "Sales",
        "priority": "Medium",
        "reason": "A commercial lead, not an outage.",
        "draft": "Draft: thanks for getting in touch.",
        "owner": "Engineering",
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


REFERENCES = [
    {
        "request": (
            "Our team has 40 employees entering the same customer details into "
            "three systems. Could you show us how this might be automated? We "
            "would like to speak next week."
        ),
        "category": Category.SALES,
        "priority": Priority.MEDIUM,
        "owner": Owner.SALES_TEAM,
        "reason": (
            "Commercial automation opportunity with a conversation requested "
            "next week, not an outage."
        ),
        "summary": (
            "Forty employees re-enter the same customer details in three "
            "systems and want to talk about automation next week."
        ),
        "draft": (
            "Draft: thank you for describing the repeated data entry. We can "
            "walk through an automation approach next week."
        ),
    },
    {
        "request": (
            "The client portal has been unavailable since this morning and our "
            "staff cannot access active customer records. Please help as soon "
            "as possible."
        ),
        "category": Category.TECHNICAL,
        "priority": Priority.URGENT,
        "owner": Owner.ENGINEERING,
        "reason": "Production access outage blocking staff from customer records now.",
        "summary": "The client portal has been down since this morning and staff cannot open customer records.",
        "draft": (
            "Draft: we see the portal has been unavailable since this morning. "
            "Engineering is treating the access outage as urgent."
        ),
    },
    {
        "request": (
            "Invoice NS-1048 appears to include the same implementation charge "
            "twice. Can someone review it before payment is processed Friday?"
        ),
        "category": Category.BILLING,
        "priority": Priority.HIGH,
        "owner": Owner.FINANCE,
        "reason": (
            "Duplicate implementation charge on invoice NS-1048 with a payment "
            "deadline this week, not an immediate outage."
        ),
        "summary": "Invoice NS-1048 may bill the same implementation charge twice, and payment is due Friday.",
        "draft": (
            "Draft: we will have Finance review invoice NS-1048 for the "
            "repeated implementation charge before Friday."
        ),
    },
    {
        "request": (
            "Can you add dark mode and change the dashboard font? There is no "
            "deadline. I am collecting ideas for a future update."
        ),
        "category": Category.OTHER,
        "priority": Priority.LOW,
        "owner": Owner.CLIENT_SUCCESS,
        "reason": "Non-urgent product idea with an explicit statement of no deadline.",
        "summary": "Request for dark mode and a dashboard font change, collected as a future idea with no deadline.",
        "draft": (
            "Draft: thank you for the dark-mode and font ideas. We have noted "
            "them for a future update, and there is no deadline on this request."
        ),
    },
    {
        "request": (
            "We accidentally uploaded a spreadsheet containing customer contact "
            "information to the wrong workspace. We need immediate help "
            "removing access."
        ),
        "category": Category.TECHNICAL,
        "priority": Priority.URGENT,
        "owner": Owner.ENGINEERING,
        "reason": (
            "Exposed customer contact data; access must be removed immediately."
        ),
        "summary": (
            "A spreadsheet of customer contact information was uploaded to the "
            "wrong workspace and access needs to be removed."
        ),
        "draft": (
            "Draft: we understand customer contact information is exposed in "
            "the wrong workspace. Engineering will help remove that access immediately."
        ),
    },
    {
        "request": (
            "I saw your company online and am interested in a custom AI "
            "reporting system. What would pricing and a typical timeline look like?"
        ),
        "category": Category.SALES,
        "priority": Priority.MEDIUM,
        "owner": Owner.SALES_TEAM,
        "reason": (
            "Inbound pricing and timeline inquiry with no emergency; still a "
            "live commercial lead."
        ),
        "summary": "Inbound question about pricing and timeline for a custom AI reporting system.",
        "draft": (
            "Draft: thank you for your interest in a custom AI reporting "
            "system. We can outline pricing and a typical timeline."
        ),
    },
]


@pytest.mark.parametrize("blank", ["", "   ", "\n\t  "])
def test_blank_input_is_rejected_before_the_model_port(blank):
    port = RecordingPort(_payload())
    with pytest.raises(TriageFailure, match="request"):
        Triage(port).run(blank)
    assert port.calls == []


@pytest.mark.parametrize("reference", REFERENCES, ids=lambda item: item["category"].value + "-" + item["priority"].value)
def test_reference_request_keeps_model_prose_and_matrix_owner(reference):
    port = RecordingPort(
        _payload(
            summary=reference["summary"],
            category=reference["category"].value,
            priority=reference["priority"].value,
            reason=reference["reason"],
            draft=reference["draft"],
            owner="Finance",
        )
    )

    result = Triage(port).run(reference["request"])

    assert result.category is reference["category"]
    assert result.priority is reference["priority"]
    assert result.owner is reference["owner"]
    assert result.owner is owner_for(result.category)
    assert result.summary == reference["summary"]
    assert result.reason == reference["reason"]
    assert result.draft == reference["draft"]
    assert port.calls == [reference["request"]]


def test_portal_outage_and_exposed_contacts_stay_distinguishable():
    outage = REFERENCES[1]
    exposure = REFERENCES[4]
    outage_result = Triage(
        RecordingPort(
            _payload(
                summary=outage["summary"],
                category="Technical",
                priority="Urgent",
                reason=outage["reason"],
                draft=outage["draft"],
            )
        )
    ).run(outage["request"])
    exposure_result = Triage(
        RecordingPort(
            _payload(
                summary=exposure["summary"],
                category="Technical",
                priority="Urgent",
                reason=exposure["reason"],
                draft=exposure["draft"],
            )
        )
    ).run(exposure["request"])

    assert outage_result.category is exposure_result.category is Category.TECHNICAL
    assert outage_result.priority is exposure_result.priority is Priority.URGENT
    assert outage_result.owner is exposure_result.owner is Owner.ENGINEERING
    assert outage_result.reason != exposure_result.reason
    assert outage_result.draft != exposure_result.draft
    assert "outage" in outage_result.reason.lower()
    assert "contact" in exposure_result.reason.lower()


def test_support_category_routes_to_client_success():
    result = Triage(
        RecordingPort(
            _payload(
                category="Support",
                priority="High",
                reason="The client cannot complete a published workflow.",
                owner="Engineering",
            )
        )
    ).run("We need help using the published workflow.")

    assert result.category is Category.SUPPORT
    assert result.owner is Owner.CLIENT_SUCCESS


@pytest.mark.parametrize(
    "overrides",
    [
        {"category": "Marketing"},
        {"priority": "Critical"},
        {"summary": "  "},
        {"reason": ""},
        {"draft": None},
    ],
)
def test_unknown_or_incomplete_model_output_is_a_visible_failure(overrides):
    port = RecordingPort(_payload(**overrides))
    with pytest.raises(TriageFailure) as caught:
        Triage(port).run("A real client request.")
    assert "Draft:" not in str(caught.value)
    assert port.calls == ["A real client request."]


def test_unparseable_payload_is_a_visible_failure_without_a_result():
    port = RecordingPort(None)
    with pytest.raises(TriageFailure, match="model"):
        Triage(port).run("A real client request.")


def test_port_failure_stays_a_visible_failure():
    port = RecordingPort(RuntimeError("connection refused"))
    with pytest.raises(TriageFailure):
        Triage(port).run("A real client request.")
