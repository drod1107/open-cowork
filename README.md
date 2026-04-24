# OpenCowork

A local-first co-working agent. Runs on your own hardware, talks to a local
LLM provider (Ollama, LM Studio, vLLM, SGLang), and exposes tools for
shell, web, browser (Playwright MCP), desktop control, and coding.
Served over Tailscale to every device on your mesh — no cloud, no auth
layer beyond the tailnet.

## Layout

```
opencowork/
├── backend/                     # FastAPI + agent loop + tools
│   ├── main.py                  # FastAPI app, WebSocket hub, static server
│   ├── agent.py                 # Streaming agent loop over OpenAI-compat API
│   ├── permissions.py           # Permission gate (ask / allow / deny, persist)
│   ├── providers.py             # Auto-discover models from provider
│   ├── scheduler.py             # APScheduler + SQLite-backed cron jobs
│   ├── config_loader.py         # Atomic TOML read/write
│   ├── config/config.toml       # Single source of truth
│   ├── db/sessions.db           # Scheduled jobs (created on first run)
│   └── tools/
│       ├── shell.py             # run_shell with allow/block lists
│       ├── web.py               # fetch_url + search_web (DDG)
│       ├── browser.py           # @playwright/mcp JSON-RPC bridge
│       ├── computer.py          # xdotool / ydotool / spectacle / scrot / mss
│       ├── coding.py            # read/write/edit + git ops with diff preview
│       └── registry.py          # Builds ToolSpec registry from the above
├── frontend/                    # React + TypeScript + Vite + Tailwind
│   └── src/components/          # Chat, ModelPicker, Scheduler, Permissions, ComputerView
├── mcp/
│   └── playwright.config.json   # Reference config for @playwright/mcp
├── install.sh                   # One-command Debian/Ubuntu setup
└── README.md
```

## Quickstart

```bash
# 1. Install system deps + Python venv + frontend build
./install.sh

# 2. Run the server (default: 0.0.0.0:7337)
source .venv/bin/activate
python -m backend.main

# 3. Open the UI
open http://localhost:7337
# or over Tailscale: http://<your-tailnet-ip>:7337
```

## Configuration

Everything lives in `backend/config/config.toml`:

- `provider` — one of `ollama`, `lmstudio`, `vllm`, `sglang`
- `base_url` — endpoint for that provider
- `[permissions]` — per-category `ask`/`allow`/`deny` defaults + pattern
  allowlists and blocklists

The UI can mutate `[permissions]` directly via the Permissions panel; the
"approve-always" button on a permission prompt persists the pattern for
future runs.

## Providers

| Provider  | Model list endpoint       |
| --------- | ------------------------- |
| Ollama    | `GET /api/tags`           |
| LM Studio | `GET /v1/models`          |
| vLLM      | `GET /v1/models`          |
| SGLang    | `GET /v1/models`          |

Vision capability is inferred from model id (e.g. `llava`, `qwen2.5-vl`,
`pixtral`). If the selected model isn't vision-capable, the computer-use
tool will still execute actions but won't pair with screenshots in a
useful loop — pick a vision model for screen-driven flows.

## Tests

Backend (pytest + httpx + respx):
```bash
.venv/bin/python -m pytest backend/tests
```

Frontend (vitest + testing-library):
```bash
cd frontend && npm test
```

Both suites run fully offline.

## Desktop control matrix

| Session          | Screenshot     | Input             |
| ---------------- | -------------- | ----------------- |
| X11              | scrot / mss    | xdotool           |
| Wayland (KDE)    | spectacle      | ydotool + xdotool |
| Windows (future) | PIL.ImageGrab  | pyautogui         |
| macOS (future)   | screencapture  | pyautogui         |

## Design notes

- **Permission gate** — every tool call passes through `PermissionGate.check(...)`.
  Allowlist match → silent execute. Blocklist match → refuse. Otherwise prompt
  the user over the WebSocket. `approve-always` / `deny-always` persist the
  pattern to `config.toml`.
- **Agent loop** — `backend/agent.py` speaks the vanilla OpenAI
  chat-completions API via the `openai` SDK pointed at the provider's
  `base_url`. Tool dispatch is hand-rolled so the flow is easy to inspect
  and test with fake completions.
- **Scheduler persistence** — APScheduler's SQLAlchemyJobStore pickles jobs,
  so the fire callable is a top-level coroutine that looks up the active
  runner in a module-level registry.

## Security posture

- Bind address is `0.0.0.0:7337` by default — expected to be used behind
  Tailscale, not exposed to the public internet. Override via the env
  vars `OPENCOWORK_HOST` / `OPENCOWORK_PORT`.
- No built-in auth — Tailscale membership is the network boundary.
- Hard-blocked shell patterns live in `config.toml`; extend them.
