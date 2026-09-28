"""Turn one written request into a complete triage or a visible failure."""

from nodeassistant.domain import Category, Priority, TriageResult, owner_for


class TriageFailure(Exception):
    """Shown on the page. This is not a draft and not a substituted owner."""


class Triage:
    """Application use case. The model port is injected; this type builds no client."""

    def __init__(self, model) -> None:
        self._model = model

    def run(self, request_text: str) -> TriageResult:
        if not isinstance(request_text, str) or not request_text.strip():
            raise TriageFailure("Enter a client request. Blank text is not triaged.")

        try:
            payload = self._model.complete(request_text)
        except TriageFailure:
            raise
        except Exception as exc:
            raise TriageFailure("The model could not complete triage.") from exc

        if payload is None:
            raise TriageFailure("The model output could not be read.")

        category = _enum_value(payload, "category", Category)
        priority = _enum_value(payload, "priority", Priority)
        return TriageResult(
            summary=_prose(payload, "summary"),
            category=category,
            priority=priority,
            reason=_prose(payload, "reason"),
            owner=owner_for(category),
            draft=_prose(payload, "draft"),
        )


def _read(payload, name: str):
    if isinstance(payload, dict):
        return payload.get(name)
    return getattr(payload, name, None)


def _prose(payload, name: str) -> str:
    value = _read(payload, name)
    if not isinstance(value, str) or not value.strip():
        raise TriageFailure(
            f"The model output is missing a {name}, so no draft was produced."
        )
    return value.strip()


def _enum_value(payload, name: str, enum_type):
    value = _read(payload, name)
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError:
            raise TriageFailure(f"The model returned an unknown {name}.") from None
    raise TriageFailure(f"The model output is missing a {name}.")
