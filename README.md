# NodeAssistant

Turn an unstructured client request into a clear next step. Paste one email, form submission, or chat message and get back:

- a short **summary**
- one **category**: Sales, Support, Billing, Technical, or Other
- one **priority** with a brief reason: Low, Medium, High, or Urgent
- one **owner**: Sales Team, Client Success, Finance, or Engineering
- a professional **draft response** for a team member to review

The tool drafts. A person sends. Nothing is stored, and request text is never logged.

## How it works

The app makes one structured call to an OpenAI-compatible chat model through LangChain. The model fills in summary, category, priority, reason, and draft. The app checks that category and priority are valid, then assigns the owner from a fixed routing matrix so requests cannot be sent to the wrong team:

| Category  | Owner          |
| --------- | -------------- |
| Sales     | Sales Team     |
| Support   | Client Success |
| Billing   | Finance        |
| Technical | Engineering    |
| Other     | Client Success |

Invalid or incomplete model output shows an error on the page instead of a guessed result.

## Requirements

- Docker Desktop (for the Compose stack with a local Ollama model), **or**
- Python 3.12+, [uv](https://docs.astral.sh/uv/), and either a running Ollama server or an OpenAI API key

## Quick start with Docker Compose

This runs the app and a local Ollama server together. No API key is needed.

```powershell
docker compose up --build
```

The first start pulls the `llama3.2` model into a Docker volume. This can take several minutes. When the `server` service is running, open <http://127.0.0.1:8000>.

Stop with Ctrl+C, then `docker compose down`. Add `-v` to also remove the downloaded model.

## Run directly on your machine

1. Install dependencies:

   ```powershell
   uv sync
   ```

2. Create your environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

   Edit `.env` and pick one option. See [Configuration](#configuration) below.

3. Start the page:

   ```powershell
   uv run --env-file .env main.py
   ```

   If `uv run` is blocked on your machine, load the variables in PowerShell and start Python directly:

   ```powershell
   Get-Content .env | Where-Object { $_ -match '^\s*[^#]' } | ForEach-Object {
     $name, $value = $_ -split '=', 2
     [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), 'Process')
   }
   .\.venv\Scripts\python.exe main.py
   ```

4. Open <http://127.0.0.1:8000>.

## Configuration

The same code talks to Ollama or OpenAI. Only three environment variables change. See `.env.example` for a ready-to-copy template.

| Variable          | Local Ollama                  | OpenAI                       |
| ----------------- | ----------------------------- | ---------------------------- |
| `OPENAI_API_BASE` | `http://127.0.0.1:11434/v1`   | `https://api.openai.com/v1`  |
| `OPENAI_API_KEY`  | any placeholder, e.g. `ollama` | your real key                |
| `OPENAI_MODEL`    | a pulled tag, e.g. `llama3.2` | a model id, e.g. `gpt-4o-mini` |

Notes:

- For Ollama, pull the model first: `ollama pull llama3.2`. If you are using the Compose stack, it is already available on `127.0.0.1:11434`.
- Never commit `.env`. It is listed in `.gitignore` and `.dockerignore`.
- Missing variables produce a clear error on the page rather than a silent failure.

## Using the page

1. Paste a client request into the text box.
2. Click **Triage**.
3. Review the summary, category, priority, reason, owner, and draft on the same page.
4. Copy the draft into your email or chat tool if it is acceptable. The page has no send button by design.

Try these sample requests:

| Request                                                    | Expected                          |
| ---------------------------------------------------------- | --------------------------------- |
| Client portal down since this morning, staff locked out    | Technical, Urgent, Engineering    |
| Invoice NS-1048 charged twice, review before Friday        | Billing, High, Finance            |
| Add dark mode and change the font, no deadline             | Other, Low, Client Success        |
| Interested in a custom AI reporting system, pricing?       | Sales, Medium, Sales Team         |

Submitting an empty box shows an error and no draft.

## Running the tests

The tests use a stand-in model and need no network, Docker, or API key.

```powershell
uv run pytest
```

or

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Project layout

```text
main.py                  Starts the page with the live model adapter
nodeassistant/
  domain.py              Category, Priority, Owner enums and the routing matrix
  triage.py              Triage use case: validates input and model output, sets owner
  adapter.py             One ChatOpenAI structured call, configured by environment
  page.py                Single HTML page on port 8000
tests/                   pytest suite
compose.yaml             App + Ollama stack
Dockerfile               Application image (non-root, port 8000)
.env.example             Environment template for running without Docker
```

## Limitations

This is a prototype. It has no authentication, no persistence, and no inbound email or chat integration.
