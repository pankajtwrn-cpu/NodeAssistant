"""Start the request-triage page."""

from nodeassistant.adapter import OpenAITriageModel
from nodeassistant.page import serve
from nodeassistant.triage import Triage


def main() -> None:
    serve(Triage(OpenAITriageModel()))


if __name__ == "__main__":
    main()
