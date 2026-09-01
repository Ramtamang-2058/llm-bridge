# llm-bridge

Local Playwright tool that drives the normal web chat UIs (Claude,
ChatGPT, Gemini...) — reading/typing like a human — so they can relay
tasks to each other. No API keys, no paid agents, no direct requests
to their servers from this script.

## Features

- **Config-driven** — URLs and CSS selectors live in `config.json`, not
  code. Add or update a service without touching Python.
- **Cross-platform** — pure Python + Playwright (bundled Chromium); works
  on Windows, Linux, and macOS.
- **Persisted login** — log in once per service, sessions are saved and
  reused.
- **Task queue** — plain SQLite (`tasks.db`), human-readable, openable in
  any SQLite viewer.
- **Finished-response detection** — waits for the streaming / "stop"
  indicator to disappear plus a text-stability check.
- **Auto-chain** — one goal, feed each reply through a route of services
  automatically (e.g. `gemini -> claude -> chatgpt`), get one final answer.
- **Three front-ends** — CLI (`cli.py`), web dashboard (`dashboard.py`,
  stdlib only), and the orchestrator loop (`orchestrator.py`).

## Setup (one time)

Linux / macOS:

```bash
./setup.sh
```

Windows:

```bat
setup.bat
```

Or manually:

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## Log in (one time per service, or when a session expires)

```bash
python login_setup.py --all        # all services
python login_setup.py claude       # just one
```

A real browser window opens — log in by hand (solve any 2FA/CAPTCHA
yourself), press Enter in the terminal, and the session is saved under
`auth/*.json` for future runs.

## Fix the selectors (important, one time)

The selectors in `config.json` are **placeholders** — web UIs change
their HTML often, so before your first real run:

1. Open each site in a normal browser.
2. Right-click the message input box -> Inspect -> copy its selector.
3. Same for the send button and (if visible) the element that appears
   only while a reply is streaming (e.g. a "Stop" button).
4. Paste the real values into `config.json` under that service.

## Add tasks

CLI:

```bash
python cli.py add gemini "Update the tracking sheet with today's completed tasks."
python cli.py add chatgpt "List my open Jira tickets in 3 bullets."
python cli.py list
```

Dashboard (open http://127.0.0.1:8000):

```bash
python dashboard.py
```

Or in Python:

```python
import tasks
tasks.init_db()
tasks.add_task("gemini", "update the sheet with today's work")
```

## Run the loop

```bash
python cli.py run                 # visible browser (watch it work)
python cli.py run --headless      # silent background
python orchestrator.py --headless # same thing
```

The browser is a fully separate process from whatever you use normally,
so it won't touch or steal focus from your own tabs.

## Auto-chain: one goal through many services

Send a single goal through an ordered route, feeding each reply into the
next service automatically, and get one final answer.

```bash
python cli.py chain "Plan our launch week" gemini claude chatgpt
```

That sends the goal to Gemini, sends Gemini's reply to Claude, sends
Claude's reply to ChatGPT, and prints the final result (plus saves the
full per-service transcript into tasks.db). Use `--headless` to run
silently.

## Project layout

```
config.json        URLs + selectors + runtime settings (edit this)
settings.py        loads config, resolves paths (cross-OS safe)
services.py        Playwright driver (send + finished-detection)
chain.py           auto-chain: send one goal through a route of services
tasks.py           SQLite task queue
orchestrator.py    the polling loop
cli.py             add/list/run from the terminal
dashboard.py       stdlib-only web UI for tasks
login_setup.py     one-time manual login per service
setup.sh / run.sh          Linux & macOS helpers
setup.bat / run.bat        Windows helpers
auth/              saved login sessions (git-ignored)
tasks.db           the SQLite queue (git-ignored)
```

## Adding a new service

Just add a block to `config.json`:

```json
"mystie": {
  "name": "My Site",
  "url": "https://example.com/chat",
  "state_file": "mystie_state.json",
  "input_selector": "...",
  "send_selector": "...",
  "streaming_selector": "...",
  "response_selector": "..."
}
```

Then `login_setup.py mystie` and it's ready — no code changes.

## Notes

- `auth/*.json` holds your live login sessions — never commit these or
  share them; treat them like passwords. They're git-ignored.
- `tasks.db` is plain SQLite you can open with any SQLite browser.
- Automating these sites' web UIs (versus their official APIs) sits
  outside what their consumer terms of use are written for. It's not
  hacking anyone's account, but keep usage to a personal pace — the
  script already adds waiting/polling rather than hammering requests.
