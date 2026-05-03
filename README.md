# OpenCowork

A local-first co-working agent. Runs on your own hardware, talks to a local
LLM provider (Ollama, LM Studio, vLLM, SGLang, NVIDIA API), and exposes tools for
shell only (MVP). Served over Tailscale to every device on your mesh — no cloud, no auth
layer beyond the tailnet.

## Current Status: MVP Phase 1 Complete ✅

**Last Updated:** 2026-05-02  
**Branch:** `mvp/features`  
**Test Results:** Backend 28 passed, Frontend 34 passed, 0 failures

## Layout (MVP - Mobile-First)

```
opencowork/
├── backend/                     # FastAPI + agent loop + tools
│   ├── main.py                  # FastAPI app, WebSocket hub, static server
│   ├── agent.py                 # Streaming agent loop (OpenAI-compatible API)
│   ├── permissions.py           # Permission gate (approve/deny, persist)
│   ├── providers.py             # Auto-discover models from provider
│   ├── config_loader.py         # Atomic TOML read/write
│   ├── config/config.toml       # Single source of truth
│   ├── tools/
│   │   ├── shell.py             # run_shell with allow/block lists
│   │   └── registry.py          # Builds ToolSpec registry
│   └── tests/                   # Backend pytest suite (28 tests)
│
├── frontend/                    # React + TypeScript + Vite + Tailwind
│   └── src/
│       ├── components/
│       │   ├── Chat.tsx            # Chat with streaming, tool calls, permissions
│       │   ├── HistoryTab.tsx       # Session history list (Phase 1)
│       │   ├── Permissions.tsx      # Tools + Permissions settings
│       │   └── ModelPicker.tsx     # Model selection dropdown
│       └── __tests__/              # Frontend vitest suite (34 tests)
│
└── README.md
```

## MVP Features Checklist ✅

- [x] **Backend:** FastAPI + WebSockets, chat streaming with model providers
- [x] **Shell Tool Only:** MVP scope - shell commands with permission gate
- [x] **Frontend:** React/TypeScript/Vite/Tailwind, 3-tab mobile UI
  - [x] Chat Tab (textarea input, send/stop button, debug icon/bar)
  - [x] History Tab (chronological session list, tap to resume, delete)
  - [x] Settings Tab (Model Providers, Tools toggle, Permissions)
- [x] **Session History:** Persistent SQLite sessions, resumable conversations
- [x] **Provider Support:** Ollama, LM Studio, vLLM, SGLang + NVIDIA API fallback
- [x] **Security:** Tailscale-only access, permission gate for shell commands
- [x] **NVIDIA API:** Credentials in `.env`, Bearer auth, consent flow
- [x] **WebSocket Protocol:** chat, stop, permission_response messages
- [x] **Stop/Kill-switch:** Stops stream + kills shell PIDs
- [x] **Config Persistence:** TOML config with tools + permissions
- [x] **Ollama Auto-start:** Binary detection + port check
- [x] **Port Auto-fallback:** Scans from 7337 upward

## Planned Features (Phase 2 - Unchecked)

- [ ] **Personas System:** Markdown persona files, system prompt injection
- [ ] **Skills System:** Markdown skill files, context injection via `/use-skill`
- [ ] **Subagents:** Agent runner, task spawning, log streaming
- [ ] **MCP Server Integration:** Model Context Protocol support
- [ ] **Additional Tools:**
  - [ ] Web tool (fetch + search)
  - [ ] Browser tool (Playwright MCP)
  - [ ] Computer tool (screenshots/input)
  - [ ] Coding tool (file edit/git operations)
- [ ] **Session Title Editing:** Inline title editing in Chat tab
- [ ] **Collapsible Tool Calls:** Toggle tool call output in chat
- [ ] **Multi-column Layout:** Responsive for tablets, landscape, desktop
- [ ] **Advanced Permissions:** Pattern matching, allow/deny/ask modes
- [ ] **Search/Filter:** In History tab

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

## Configuration (MVP)

Everything lives in `backend/config/config.toml`:

```toml
provider = "ollama"
base_url = "http://localhost:11434"

[tools]
shell = true

[permissions.shell]
allowed_commands = ["ls*", "pwd", "echo*", "cat*", "grep", "git status", "git diff*"]
blocked_commands = ["rm -rf /*", "mkfs*", "dd if=*", ":(){:|:&};:"]
```

- **NVIDIA API:** Credentials stored in `.env` (never in config.toml):
  ```
  NVIDIA_API_KEY=nvapi-xxxxx
  NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
  NVIDIA_MODEL=deepseek-ai/deepseek-v4-pro
  ```

## Providers (MVP)

| Provider  | Model list endpoint       | Notes                    |
| --------- | ------------------------- | ------------------------- |
| Ollama    | `GET /api/tags`           | Default, auto-starts if binary exists |
| LM Studio | `GET /v1/models`          | OpenAI-compatible          |
| vLLM      | `GET /v1/models`          | OpenAI-compatible          |
| SGLang    | `GET /v1/models`          | OpenAI-compatible          |
| NVIDIA    | `GET /v1/models`          | Bearer auth, `.env` credentials |

## Tests

Three layers, run independently:

**Backend** (pytest - 28 tests passing):
```bash
.venv/bin/pytest backend/tests/ -v
```
Covers: config + permissions + shell tool + provider discovery + WebSocket protocol + stop/killswitch.

**Frontend integration** (vitest - 34 tests passing):
```bash
cd frontend && npm test
```
The headline file is `src/__tests__/App.integration.test.tsx`: it mounts the
real `<App/>` and drives it through an in-memory fake server that replaces
both `fetch` (REST) and `WebSocket`. Verifies the full flow end-to-end:
WebSocket connect, model load + select, queued sends flushed on open, streaming
tokens, tool call cards, permission approval round-trip, error handling,
panel switching, stop button, debug bar, textarea input.

**End-to-end** (Future - Phase 2):
```bash
cd frontend
npm run e2e  # Playwright against real FastAPI server
```

## Security Posture (MVP)

- Bind address is `0.0.0.0:7337` by default — expected to be used behind
  Tailscale, not exposed to the public internet. Override via env vars
  `OPENCOWORK_HOST` / `OPENCOWORK_PORT`.
- No built-in auth — Tailscale membership is the network boundary.
- Hard-blocked shell patterns live in `config.toml`; extend them.
- NVIDIA API keys stored in `.env` (never in config.toml or codebase).
  `.env` is in `.gitignore` to prevent accidental commits.

## Design Notes (MVP)

- **Permission gate** — every tool call passes through `PermissionGate.check(...)`.
  Allowlist match → silent execute. Blocklist match → refuse. Otherwise prompt
  the user over the WebSocket. `approve-always` / `deny-always` persist the pattern to `config.toml`.
  UI sends: `this time` (→ approve), `always` (→ approve-always), `no` (→ deny), `never` (→ deny-always).

- **Agent loop** — `backend/agent.py` speaks the vanilla OpenAI
  chat-completions API via the `openai` SDK pointed at the provider's
  `base_url`. Tool dispatch is hand-rolled so the flow is easy to inspect
  and test with fake completions.

- **Mobile-first** — Strictly single-column, full width on mobile. Bottom tab bar
  fixed, no dead space. Desktop UI is incidental (Phase 2 for responsive layouts).
