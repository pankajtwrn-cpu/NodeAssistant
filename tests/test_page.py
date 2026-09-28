"""In-process page check. No browser and no live model."""

import html
import logging

import pytest

from nodeassistant.page import handle_submission
from nodeassistant.triage import Triage, TriageFailure

SUMMARY = "Pricing & timeline for a reporting system."
CATEGORY = "Sales"
PRIORITY = "Medium"
REASON = "Inbound pricing inquiry with no emergency; still a live lead."
OWNER = "Sales Team"
DRAFT = "Draft: we can outline pricing and a typical timeline."
REQUEST = "What would pricing and a typical timeline look like?"


class Port:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def complete(self, request_text: str):
        self.calls.append(request_text)
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def _ok_payload():
    return Port(
        type(
            "Fields",
            (),
            {
                "summary": SUMMARY,
                "category": CATEGORY,
                "priority": PRIORITY,
                "reason": REASON,
                "draft": DRAFT,
            },
        )()
    )


def test_page_shows_all_five_outputs_and_rejects_empty_input():
    port = _ok_payload()
    page = handle_submission(REQUEST, Triage(port))

    assert html.escape(SUMMARY) in page
    assert CATEGORY in page
    assert PRIORITY in page
    assert html.escape(REASON) in page
    assert OWNER in page
    assert html.escape(DRAFT) in page
    assert 'id="summary"' in page
    assert 'id="category"' in page
    assert 'id="priority"' in page
    assert 'id="reason"' in page
    assert 'id="owner"' in page
    assert 'id="draft"' in page
    assert "Draft" in page
    assert "not been sent" in page
    assert "<button" in page
    assert "Send</button>" not in page
    assert port.calls == [REQUEST]

    empty = handle_submission("   ", Triage(port))
    assert "request" in empty.lower()
    assert 'id="triage-error"' in empty
    assert 'id="draft"' not in empty
    assert DRAFT not in empty
    assert port.calls == [REQUEST]


def test_invalid_output_and_missing_configuration_stay_on_the_page_without_a_draft():
    unknown = handle_submission(
        REQUEST,
        Triage(Port(type("Fields", (), {
            "summary": SUMMARY,
            "category": "Marketing",
            "priority": PRIORITY,
            "reason": REASON,
            "draft": DRAFT,
        })())),
    )
    assert 'id="triage-error"' in unknown
    assert 'id="draft"' not in unknown
    assert DRAFT not in unknown

    missing_key = handle_submission(
        REQUEST,
        Triage(Port(TriageFailure("OPENAI_API_KEY is not set. Set it before triage."))),
    )
    assert "OPENAI_API_KEY" in missing_key
    assert 'id="triage-error"' in missing_key
    assert 'id="draft"' not in missing_key
    assert DRAFT not in missing_key


def test_serve_listens_on_port_8000(monkeypatch):
    bound = {}

    class FakeServer:
        def __init__(self, address, handler):
            bound["address"] = address
            bound["handler"] = handler

        def serve_forever(self):
            bound["serving"] = True

    monkeypatch.setattr("nodeassistant.page.ThreadingHTTPServer", FakeServer)

    from nodeassistant.page import serve

    serve(Triage(Port(type("Fields", (), {})())), port=8000)

    assert bound["address"] == ("0.0.0.0", 8000)
    assert bound["serving"] is True
    handler = bound["handler"]
    assert hasattr(handler, "do_GET")
    assert hasattr(handler, "do_POST")


def test_main_starts_the_triage_page_on_port_8000(monkeypatch):
    captured = {}

    def fake_serve(triage, host="0.0.0.0", port=8000):
        captured["triage"] = triage
        captured["port"] = port

    monkeypatch.setattr("nodeassistant.page.serve", fake_serve)

    from main import main

    main()

    assert captured["port"] == 8000
    assert type(captured["triage"]._model).__name__ == "OpenAITriageModel"


def test_success_log_records_routing_and_omits_request_text_and_draft(caplog):
    caplog.set_level(logging.DEBUG)
    handle_submission(REQUEST, Triage(_ok_payload()))

    assert "Sales" in caplog.text
    assert "Medium" in caplog.text
    assert "Sales Team" in caplog.text
    assert REQUEST not in caplog.text
    assert DRAFT not in caplog.text
    assert SUMMARY not in caplog.text
