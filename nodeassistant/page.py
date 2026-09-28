"""One local page: paste a request, read the triage, review the draft."""

import html
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from nodeassistant.triage import TriageFailure

logger = logging.getLogger("nodeassistant.page")


def handle_submission(request_text: str, triage) -> str:
    """Render the same page with a complete triage or a visible failure."""
    try:
        result = triage.run(request_text)
    except TriageFailure as exc:
        return _render(request_text, error=str(exc))

    logger.info(
        "triage ran category=%s priority=%s owner=%s",
        result.category.value,
        result.priority.value,
        result.owner.value,
    )
    return _render(request_text, result=result)


def serve(triage, host: str = "0.0.0.0", port: int = 8000) -> None:
    """Listen for the triage page. The process stays up until interrupted."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._send(_render(""))

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            fields = parse_qs(raw, keep_blank_values=True)
            request_text = fields.get("request", [""])[0]
            self._send(handle_submission(request_text, triage))

        def _send(self, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    ThreadingHTTPServer((host, port), Handler).serve_forever()


_STYLE = """
:root {
  --bg: #f4f6f8;
  --card: #ffffff;
  --ink: #1f2933;
  --muted: #616e7c;
  --line: #d9e2ec;
  --accent: #1f5fbf;
  --accent-dark: #174a96;
  --error-bg: #fdecec;
  --error-ink: #8a1c1c;
  --error-line: #f3b4b4;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 40px 16px 64px;
  background: var(--bg);
  color: var(--ink);
  font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, sans-serif;
}
main { max-width: 760px; margin: 0 auto; }
header { margin-bottom: 24px; }
h1 { margin: 0 0 6px; font-size: 26px; font-weight: 600; letter-spacing: -0.01em; }
header p { margin: 0; color: var(--muted); }
.card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 24px 28px;
  margin-bottom: 20px;
}
label { display: block; font-weight: 600; margin-bottom: 8px; }
textarea {
  width: 100%;
  min-height: 170px;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  font: inherit;
  color: var(--ink);
  resize: vertical;
}
textarea:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(31, 95, 191, 0.15); }
button {
  margin-top: 14px;
  padding: 10px 22px;
  border: 0;
  border-radius: 8px;
  background: var(--accent);
  color: #fff;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
button:hover { background: var(--accent-dark); }
#triage-error {
  margin: 0 0 20px;
  padding: 12px 16px;
  border: 1px solid var(--error-line);
  border-radius: 8px;
  background: var(--error-bg);
  color: var(--error-ink);
}
h2 { margin: 0 0 6px; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }
.field { margin-bottom: 20px; }
.field p { margin: 0; }
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px; }
.grid .field { margin: 0; padding: 14px 16px; border: 1px solid var(--line); border-radius: 8px; background: #fafbfc; }
.grid .field p { font-weight: 600; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 14px; }
.badge-low { background: #e3f1e6; color: #1e6b32; }
.badge-medium { background: #e6effb; color: #1f4f9c; }
.badge-high { background: #fdf0dc; color: #8a4b00; }
.badge-urgent { background: #fbe3e3; color: #9b1c1c; }
.draft { padding: 16px 18px; border: 1px solid var(--line); border-left: 4px solid var(--accent); border-radius: 8px; background: #fafbfc; }
#draft-notice { margin: 0 0 10px; font-size: 14px; color: var(--muted); }
#draft { white-space: pre-wrap; }
@media (max-width: 600px) { .grid { grid-template-columns: 1fr; } .card { padding: 20px; } }
"""


def _render(request_text: str, result=None, error: str | None = None) -> str:
    error_html = ""
    if error:
        error_html = f'<p id="triage-error" role="alert">{html.escape(error)}</p>'

    result_html = ""
    if result is not None:
        priority = result.priority.value
        result_html = f"""
<section id="triage-result" class="card">
  <div class="field">
    <h2>Summary</h2>
    <p id="summary">{html.escape(result.summary)}</p>
  </div>
  <div class="grid">
    <div class="field">
      <h2>Category</h2>
      <p id="category">{html.escape(result.category.value)}</p>
    </div>
    <div class="field">
      <h2>Priority</h2>
      <p id="priority" class="badge badge-{priority.lower()}">{html.escape(priority)}</p>
    </div>
    <div class="field">
      <h2>Owner</h2>
      <p id="owner">{html.escape(result.owner.value)}</p>
    </div>
  </div>
  <div class="field">
    <h2>Reason</h2>
    <p id="reason">{html.escape(result.reason)}</p>
  </div>
  <div class="field draft">
    <h2>Draft response</h2>
    <p id="draft-notice">This is a draft for review. It has not been sent.</p>
    <p id="draft">{html.escape(result.draft)}</p>
  </div>
</section>
"""

    pasted = html.escape(request_text or "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Request triage</title>
  <style>{_STYLE}</style>
</head>
<body>
  <main>
    <header>
      <h1>Request triage</h1>
      <p>Paste a client request to get a summary, category, priority, owner, and a draft reply to review.</p>
    </header>
    <form method="post" action="/" class="card">
      <label for="request">Client request</label>
      <textarea id="request" name="request" rows="8" placeholder="Paste the email, form submission, or chat message here.">{pasted}</textarea>
      <button type="submit">Triage</button>
    </form>
    {error_html}
    {result_html}
  </main>
</body>
</html>
"""
