"""Live adapter configuration. The stand-in client never touches the network."""

import logging
from types import SimpleNamespace

import pytest

from nodeassistant.domain import Category, Priority
from nodeassistant.triage import TriageFailure


REQUEST = "Customer contact spreadsheet in the wrong workspace."
DRAFT = "Draft: we will help remove access."


class ExplodingClient:
    def __init__(self, **kwargs):
        raise AssertionError(f"ChatOpenAI should not be constructed, got {kwargs}")


class RecordingClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        RecordingClient.constructed.append(kwargs)

    constructed: list = []

    def with_structured_output(self, schema):
        RecordingClient.schema = schema

        class _Once:
            calls = 0

            def invoke(_self, messages):
                _Once.calls += 1
                RecordingClient.messages = messages
                RecordingClient.invocations += 1
                outcome = RecordingClient.outcome
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome

        return _Once()


def _install_client(monkeypatch, client_type):
    import nodeassistant.adapter as adapter

    monkeypatch.setattr(adapter, "ChatOpenAI", client_type)


def _ready_env(monkeypatch, *, base="http://ollama:11434/v1"):
    monkeypatch.setenv("OPENAI_MODEL", "llama3.2")
    monkeypatch.setenv("OPENAI_API_KEY", "ollama")
    if base is None:
        monkeypatch.delenv("OPENAI_API_BASE", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    else:
        monkeypatch.setenv("OPENAI_API_BASE", base)


@pytest.fixture(autouse=True)
def _reset_recorder():
    RecordingClient.constructed = []
    RecordingClient.schema = None
    RecordingClient.messages = None
    RecordingClient.invocations = 0
    RecordingClient.outcome = SimpleNamespace(
        summary="Portal access is down.",
        category=Category.TECHNICAL,
        priority=Priority.URGENT,
        reason="Production access outage blocking staff now.",
        draft=DRAFT,
    )
    yield


def test_module_does_not_name_a_second_provider_or_a_hardcoded_endpoint():
    import inspect

    import nodeassistant.adapter as adapter

    source = inspect.getsource(adapter)
    assert "langchain_ollama" not in source
    assert "laya" not in source
    assert "11434" not in source
    assert "api.openai.com" not in source


@pytest.mark.parametrize("model_name", ["", "   ", None])
def test_missing_model_name_is_a_visible_failure(monkeypatch, model_name):
    _install_client(monkeypatch, ExplodingClient)
    monkeypatch.setenv("OPENAI_API_KEY", "ollama")
    if model_name is None:
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
    else:
        monkeypatch.setenv("OPENAI_MODEL", model_name)

    from nodeassistant.adapter import OpenAITriageModel

    with pytest.raises(TriageFailure, match="OPENAI_MODEL"):
        OpenAITriageModel().complete(REQUEST)


def test_missing_api_key_is_a_visible_failure(monkeypatch):
    _install_client(monkeypatch, ExplodingClient)
    monkeypatch.setenv("OPENAI_MODEL", "llama3.2")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from nodeassistant.adapter import OpenAITriageModel

    with pytest.raises(TriageFailure, match="OPENAI_API_KEY"):
        OpenAITriageModel().complete(REQUEST)


def test_one_structured_call_uses_env_model_and_leaves_credentials_to_the_client(
    monkeypatch,
):
    _install_client(monkeypatch, RecordingClient)
    _ready_env(monkeypatch)

    from nodeassistant.adapter import OpenAITriageModel

    result = OpenAITriageModel().complete(REQUEST)

    assert result.summary == "Portal access is down."
    assert result.category is Category.TECHNICAL
    assert result.priority is Priority.URGENT
    assert result.reason.startswith("Production access outage")
    assert result.draft == DRAFT
    assert not hasattr(result, "owner")
    assert RecordingClient.invocations == 1
    kwargs = RecordingClient.constructed[0]
    assert kwargs["model"] == "llama3.2"
    assert "api_key" not in kwargs
    assert "openai_api_key" not in kwargs
    assert "base_url" not in kwargs
    assert "openai_api_base" not in kwargs
    assert kwargs["stream_usage"] is False
    fields = set(RecordingClient.schema.model_fields)
    assert fields == {"summary", "category", "priority", "reason", "draft"}
    assert RecordingClient.schema.model_fields["category"].annotation is Category
    assert RecordingClient.schema.model_fields["priority"].annotation is Priority
    assert REQUEST in RecordingClient.messages[1].content


def test_stream_usage_is_not_forced_on_when_no_custom_base_url(monkeypatch):
    _install_client(monkeypatch, RecordingClient)
    _ready_env(monkeypatch, base=None)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")

    from nodeassistant.adapter import OpenAITriageModel

    OpenAITriageModel().complete(REQUEST)

    kwargs = RecordingClient.constructed[0]
    assert kwargs["model"] == "gpt-4.1-mini"
    assert kwargs.get("stream_usage") is not True
    assert "base_url" not in kwargs


def test_unreachable_endpoint_is_a_visible_failure(monkeypatch):
    _install_client(monkeypatch, RecordingClient)
    _ready_env(monkeypatch)
    RecordingClient.outcome = ConnectionError("connection refused")

    from nodeassistant.adapter import OpenAITriageModel

    with pytest.raises(TriageFailure, match="reached") as caught:
        OpenAITriageModel().complete(REQUEST)
    assert REQUEST not in str(caught.value)
    assert DRAFT not in str(caught.value)


def test_schema_mismatch_is_a_visible_failure(monkeypatch):
    _install_client(monkeypatch, RecordingClient)
    _ready_env(monkeypatch)
    RecordingClient.outcome = None

    from nodeassistant.adapter import OpenAITriageModel

    with pytest.raises(TriageFailure, match="schema") as caught:
        OpenAITriageModel().complete(REQUEST)
    assert REQUEST not in str(caught.value)


def test_other_model_call_errors_are_visible_and_are_not_called_a_schema_mismatch(
    monkeypatch,
):
    _install_client(monkeypatch, RecordingClient)
    _ready_env(monkeypatch)

    class MissingModel(Exception):
        pass

    RecordingClient.outcome = MissingModel("model is not installed")

    from nodeassistant.adapter import OpenAITriageModel

    with pytest.raises(TriageFailure, match="failed") as caught:
        OpenAITriageModel().complete(REQUEST)
    message = str(caught.value)
    assert "schema" not in message.lower()
    assert REQUEST not in message
    assert DRAFT not in message


def test_adapter_does_not_log_the_request_or_the_draft(monkeypatch, caplog):
    _install_client(monkeypatch, RecordingClient)
    _ready_env(monkeypatch)
    caplog.set_level(logging.DEBUG)

    from nodeassistant.adapter import OpenAITriageModel

    OpenAITriageModel().complete(REQUEST)

    assert REQUEST not in caplog.text
    assert DRAFT not in caplog.text
