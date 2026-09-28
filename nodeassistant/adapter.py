"""One OpenAI-compatible structured triage call. The environment picks the server."""

import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from nodeassistant.domain import Category, Priority
from nodeassistant.triage import TriageFailure

_INSTRUCTIONS = (
    "Triage one client request for a professional-services team. "
    "summary is one sentence describing the request in two or three words. Add [URGENT] if the request is urgent."
    "category is exactly one of Sales, Support, Billing, Technical, Other. "
    "priority is exactly one of Low, Medium, High, Urgent. "
    "reason explains why that category and priority fit, using the specifics "
    "of this request so different incidents stay distinguishable. "
    "draft is a professional first response for a person to review. "
    "Do not claim the issue is already fixed. Do not claim a message was sent. "
    "Do not choose an owner."
)


class StructuredTriage(BaseModel):
    """Fields the model may fill. Owner is not one of them."""

    model_config = ConfigDict(extra="ignore")

    summary: str
    category: Category
    priority: Priority
    reason: str
    draft: str

    @field_validator("summary", "reason", "draft")
    @classmethod
    def _prose_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("required")
        return value


class OpenAITriageModel:
    """Model port backed by a single ChatOpenAI structured completion."""

    def complete(self, request_text: str) -> StructuredTriage:
        model_name = os.environ.get("OPENAI_MODEL", "").strip()
        if not model_name:
            raise TriageFailure(
                "OPENAI_MODEL is not set. Set the model name before triage."
            )
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            raise TriageFailure(
                "OPENAI_API_KEY is not set. Set it before triage."
            )

        client_kwargs: dict = {"model": model_name}
        if os.environ.get("OPENAI_API_BASE", "").strip():
            client_kwargs["stream_usage"] = False

        messages = [
            SystemMessage(_INSTRUCTIONS),
            HumanMessage(request_text),
        ]
        try:
            structured = ChatOpenAI(**client_kwargs).with_structured_output(
                StructuredTriage
            )
            parsed = structured.invoke(messages)
        except Exception as exc:
            raise _failure_for(exc) from exc

        if parsed is None:
            raise TriageFailure("The model output did not match the triage schema.")
        try:
            if isinstance(parsed, dict):
                return StructuredTriage.model_validate(parsed)
            if isinstance(parsed, StructuredTriage):
                return parsed
            return StructuredTriage.model_validate(parsed, from_attributes=True)
        except ValidationError as exc:
            raise TriageFailure(
                "The model output did not match the triage schema."
            ) from exc


def _failure_for(exc: Exception) -> TriageFailure:
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)) or _named_unreachable(
        exc
    ):
        return TriageFailure("The model endpoint could not be reached.")
    name = type(exc).__name__
    if "Validation" in name or "Parser" in name or "Schema" in name:
        return TriageFailure("The model output did not match the triage schema.")
    return TriageFailure("The triage model call failed.")


def _named_unreachable(exc: Exception) -> bool:
    name = type(exc).__name__
    return "Connection" in name or "Timeout" in name or "ConnectError" in name
