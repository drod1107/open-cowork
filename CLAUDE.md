# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What this is

OpenCowork is a minimalist local-first AI co-working agent. It connects to a local Ollama instance (or any OpenAI-compatible provider) and exposes a React chat UI with tool use, a task scheduler, permission gating, computer view, session history, personas, skills, and MCP server integration. The architecture is intentionally small and easy to extend.

---

## Commands

```bash
# Backend — run from repo root
.venv/bin/python -m backend.main          # start server on http://localhost:7337
.venv/bin/pytest                          # run all backend tests
.venv/bin/pytest backend/tests/test_X.py -x -q  # run one test file

# Frontend — run from frontend/
npm run dev      # dev server on :5173 (proxies /api and /ws to :7337)
npm run build    # compile to frontend/dist/ (served by backend in prod)
npm test         # Vitest (run once)
npm run test:watch
npx tsc --noEmit # type-check only

# One-command run (builds frontend if needed, then starts server)
./run.sh

# MCP server installer
./install-mcp.sh <github-url-or-local-path>
```

Install dependencies (only needed once or after fresh clone):
```bash
./install.sh    # creates .venv, installs Python deps, runs npm install in frontend/
```

---

## Architecture

### Backend (`backend/`)

| File | Role |
|------|------|
| `main.py` | FastAPI app entry point. `HubState` owns the WebSocket set, permission futures, scheduler, and model selection. `lifespan` boots everything. All REST endpoints are top-level `@app.*` functions. |
| `agent.py` | `Agent.run_stream(user_message, history)` — async generator that calls the LLM, dispatches tool calls, and yields dict events: `token`, `final`, `tool_call`, `tool_result`, `error`. |
| `sessions.py` | aiosqlite CRUD for the `sessions` table in `backend/db/sessions.db`. Functions: `init_db`, `create_session`, `append_message`, `get_session`, `list_sessions`, `delete_session`, `update_session_metadata`. |
| `permissions.py` | `PermissionGate` intercepts every tool call, checks allow/block rules, and optionally prompts the user via the WebSocket. Supports ephemeral per-connection dirs. |
| `scheduler.py` | Thin APScheduler wrapper. Jobs persist in `backend/db/sessions.db` (the `apscheduler_jobs` table). |
| `config_loader.py` | Reads/writes `backend/config/config.toml` (TOML, thread-safe). |
| `providers.py` | `ProviderClient.list_models()` — queries Ollama/LM Studio/vLLM/SGLang for available models. |
| `tools/` | `shell.py`, `web.py`, `browser.py`, `computer.py`, `coding.py`. Each exposes a `build_*()` function that returns `ToolSpec` instances. `registry.py` assembles them all. |
| `personas/` | Markdown persona files. Frontmatter: `name`, `slug`, `description`, `tools` (list). Body is the system prompt text. See "Persona system" below. |
| `skills/` | Markdown skill files. Frontmatter: `name`, `slug`, `description`. Body is the skill prompt injected into context on `/use-skill <slug>`. |
| `mcp/` | MCP client subsystem. `client.py` — stdio/HTTP MCP client. `registry.py` — tracks installed MCP servers from `backend/config/mcp_servers.toml`. |

**WebSocket protocol** (`/ws`): all frames are JSON with a `type` key.

| Direction | `type` | Payload |
|-----------|--------|---------|
| Client → Server | `chat` | `{ text, session_id? }` |
| Client → Server | `permission_response` | `{ id, decision }` |
| Client → Server | `add_dir` | `{ path }` |
| Client → Server | `inject_context` | `{ session_id, current_session_id? }` |
| Client → Server | `ping` | — |
| Server → Client | `token` | `{ text }` |
| Server → Client | `final` | `{ text }` |
| Server → Client | `session_id` | `{ session_id }` |
| Server → Client | `session_title` | `{ session_id, title }` |
| Server → Client | `tool_call` | `{ tool, input }` |
| Server → Client | `tool_result` | `{ tool, output }` |
| Server → Client | `permission_request` | `{ request: { id, category, action, description } }` |
| Server → Client | `dir_added` | `{ path, ok, error? }` |
| Server → Client | `context_injected` | `{ from_title, message_count }` |
| Server → Client | `error` | `{ error }` |
| Server → Client | `pong` | — |

**REST endpoints**:
- `GET /api/health`
- `GET /api/models?force=` / `POST /api/models/select`
- `GET /api/schedules` / `POST /api/schedules` / `DELETE /api/schedules/{id}`
- `GET /api/sessions` / `GET /api/sessions/{id}` / `PATCH /api/sessions/{id}` / `DELETE /api/sessions/{id}`
- `GET /api/config` / `PUT /api/config`
- `GET /api/personas` / `GET /api/personas/{slug}`
- `GET /api/skills` / `POST /api/skills`

### Frontend (`frontend/src/`)

| File | Role |
|------|------|
| `App.tsx` | Root component. Owns `AgentSocket`, panel state, active session state, active persona. Mounts `Sidebar` (left), `Chat` (center), right panel. |
| `components/Chat.tsx` | Streams `AgentEvent`s into a list of `ChatItem`s. Slash commands: `/add-dir`, `/get-chat`, `/use-skill`. |
| `components/Sidebar.tsx` | Session list panel. Inline title editing on active session. Props: `activeSessionId`, `onSelect`, `onDelete`, `onRename`, `refreshKey`. |
| `components/SessionTitle.tsx` | Click-to-edit title bar above the chat area for the active session. |
| `components/PersonaPicker.tsx` | Dropdown to select active persona. Lives in the header. |
| `components/ModelPicker.tsx` | Dropdown to select active model. |
| `lib/ws.ts` | `AgentSocket` class. `AgentEvent` and `OutgoingMessage` union types. |
| `lib/api.ts` | Typed fetch wrappers for all REST endpoints. |

### Database

`backend/db/sessions.db` (SQLite):
- `apscheduler_jobs` — owned by APScheduler, do not touch
- `sessions` — `(id TEXT PK, created_at, updated_at, messages JSON, metadata JSON)`

---

## Testing patterns

**Backend** — pytest-asyncio in `auto` mode. Key fixture is `tmp_config` (in `conftest.py`): writes a temp TOML and returns its `Path`. Patch `DB_PATH` for sessions the same way scheduler patches its `DB_PATH`:
```python
monkeypatch.setattr(sessions_mod, "DB_PATH", Path(tmp_config).parent / "sessions.db")
```

**Frontend** — Vitest + testing-library. `MockSocket` in `Chat.test.tsx` is the standard stub for `AgentSocket`. For components that call `fetch`, `vi.mock("../lib/api", ...)`.

---

## Persona system

Persona files live in `backend/personas/<slug>.md`. Format:

```markdown
---
name: Human-readable Name
slug: machine-slug
description: One-line description shown in UI picker
tools:
  - shell
  - filesystem
  - web
  - coding
---

You are [persona description here]. Your behavior rules, tool preferences,
response style, etc.
```

**How it works:**
1. `GET /api/personas` returns all persona stubs (name, slug, description).
2. The active persona slug is stored in `config.toml` under `active_persona`.
3. `HubState.build_agent()` calls `load_persona(slug)` to get the system prompt body, which replaces (or prepends to) the user-configured `system_prompt` from config.
4. `PersonaPicker` in the header calls `POST /api/config` with the updated `active_persona` to persist selection.

**Installed personas** (in `backend/personas/`):
- `claude-code.md` — Software engineering assistant matching Claude Code behavior for smaller models
- `perplexity.md` — Search and research aggregator; uses web tools heavily, returns structured summaries
- `code-pm.md` — Project Manager: plans work, breaks epics into tasks, delegates to specialized agents
- `code-po.md` — Product Owner: translates user requirements into stories/features/acceptance criteria
- `code-qa.md` — QA Engineer: writes tests, reviews for edge cases, validates acceptance criteria
- `code-fe.md` — Frontend Engineer: React/TypeScript/CSS specialist, focuses on UI/UX and accessibility
- `code-be.md` — Backend Engineer: API design, Python/FastAPI, database schema, performance
- `code-db.md` — Database Engineer: schema design, migrations, query optimization, indexing
- `code-devops.md` — DevOps/Platform: CI/CD, Docker, deployment, infrastructure, monitoring

---

## Skill system

Skill files live in `backend/skills/<slug>.md`. Format:

```markdown
---
name: Human-readable Name
slug: machine-slug
description: One-line description
---

The skill prompt that gets injected into the conversation as context when invoked.
```

**How it works:**
1. User types `/use-skill <slug>` in the chat input (autocompletes from `GET /api/skills`).
2. The selected skill's prompt is sent as a `chat` message with special metadata, OR injected as a context block via the `inject_context` WS path.
3. `POST /api/skills` (body: `{ name, slug, description, content }`) creates a new skill file. This is what `/create-skill` calls.

**Creating skills via `/create-skill`:**
- User types `/create-skill` → a modal/form appears with fields: Name, Slug, Description, Prompt body
- On submit, sends `POST /api/skills` which writes `backend/skills/<slug>.md`
- The skill is immediately available in `/use-skill` autocomplete

---

## MCP server integration

MCP (Model Context Protocol) servers are external processes that expose tools to the agent via JSON-RPC (stdio or HTTP transport).

### Installation

```bash
./install-mcp.sh <github-url-or-local-path> [--name <name>]
```

`install-mcp.sh` does exactly:
1. If arg is a URL: `git clone <url> backend/mcp/servers/<name>`
2. If arg is a path: copies/symlinks it to `backend/mcp/servers/<name>`
3. Detects type:
   - `package.json` present → Node.js: runs `npm install`
   - `pyproject.toml` or `requirements.txt` → Python: runs `pip install`
4. Reads `mcp-server.json` (or `package.json` `"main"` field) for the entry point
5. Appends an entry to `backend/config/mcp_servers.toml`:
   ```toml
   [[mcp_servers]]
   name = "my-server"
   command = ["node", "backend/mcp/servers/my-server/index.js"]
   transport = "stdio"
   enabled = true
   ```
6. Prints instructions to restart the backend.

### Runtime

`backend/mcp/client.py` — `MCPClient` class:
- On startup (in `lifespan`), reads `mcp_servers.toml` and starts each enabled server as a subprocess.
- Calls `tools/list` to discover available tools.
- Wraps each discovered tool as a `ToolSpec` and registers it with the tool registry.
- Forwards tool calls to the subprocess via JSON-RPC, returns results.

`backend/mcp/registry.py` — tracks `MCPClient` instances, shuts them down on lifespan exit.

---

## Slash commands reference

All slash commands appear in the chat input autocomplete when the user types `/`.

| Command | Effect |
|---------|--------|
| `/add-dir <path>` | Grant this chat session filesystem access to `<path>` and its subdirectories (ephemeral — lost on page reload). |
| `/get-chat <title>` | Fuzzy-search existing session titles. Selecting one injects that session's message history as context into the current chat. |
| `/use-skill <slug>` | Fuzzy-search installed skills. Selecting one injects the skill prompt as context. |
| `/create-skill` | Opens an inline form to define and save a new skill to `backend/skills/`. |
| `/create-persona` | Opens an inline form to define and save a new persona to `backend/personas/`. |
| `/create-mcp` | Opens a guided form to install a new MCP server (calls `install-mcp.sh` programmatically). |

---

## Active work plan

Items are checked when complete. This section is the source of truth for paused work.

### ✅ DONE — Session history & context management
- `backend/sessions.py` — full CRUD, `update_session_metadata`
- Session REST endpoints in `main.py` (GET, PATCH, DELETE, list)
- `_build_history()` for conversation context injection
- `context_block` message type for `/get-chat` injected context
- AI-generated session titles via background `asyncio.create_task`
- `Sidebar.tsx` — shows sessions with title/date, delete button
- `Chat.tsx` — autoscroll, `/add-dir`, `/get-chat` with fuzzy session autocomplete
- `SessionTitle.tsx` — click-to-edit title bar above chat
- `App.tsx` — full wiring of session lifecycle
- 70 backend tests passing

### ✅ DONE — Session title editing fix
- `Sidebar.tsx`: hover reveals ✎ pencil + × delete buttons; click pencil → inline input, Enter/blur saves
- `SessionTitle` above chat: always visible (not gated on activeSessionId), shows "New chat" placeholder, "✎ rename" hint on hover
- `App.tsx`: `handleSidebarRename` → `api.updateSession` → updates both sidebar and header title
- `onRename` prop added to Sidebar

### ✅ DONE — Persona system
- `backend/personas/` created with 9 persona files: `claude-code`, `perplexity`, `code-pm`, `code-po`, `code-qa`, `code-fe`, `code-be`, `code-db`, `code-devops`
- `GET /api/personas` and `GET /api/personas/{slug}` endpoints
- `_parse_frontmatter`, `_load_persona`, `_list_personas` helpers in `main.py`
- `HubState.build_agent()` injects persona body as system prompt when `cfg.active_persona` is set
- `PersonaPicker.tsx` — select dropdown in header, persists to config via `PUT /api/config`
- 6 tests in `test_personas.py`

### ✅ DONE — Skill system (core)
- `backend/skills/` created
- `GET /api/skills` and `POST /api/skills` endpoints
- `/use-skill` slash command in Chat: fuzzy autocomplete of installed skills
- `/create-skill` slash command: inline form (Name, Slug, Description, Prompt) — saves via `POST /api/skills`
- `api.ts`: `listSkills`, `createSkill`
- 5 tests in `test_skills.py`

### ✅ DONE — MCP server integration (infrastructure)
- `install-mcp.sh`: clones GitHub URL or copies local path, detects Node.js/Python, installs deps, appends to `backend/config/mcp_servers.toml`
- `backend/mcp/client.py`: `MCPClient` — stdio JSON-RPC client, `start()` discovers tools, `call_tool()` dispatches calls
- `backend/mcp/registry.py`: `MCPRegistry` — reads config, starts all enabled servers, exposes tool specs

### 📋 TODO — MCP runtime wiring (remaining)
- [ ] Wire `MCPRegistry` into `lifespan` in `main.py` (start on boot, stop on shutdown)
- [ ] Convert `MCPRegistry.get_tool_specs()` into `ToolSpec` objects in `build_registry()`
- [ ] `/create-mcp` slash command in Chat: URL/path input form, calls `POST /api/mcp/install`
- [ ] `POST /api/mcp/install` endpoint: runs `install-mcp.sh` as subprocess, streams output
- [ ] Tests for MCPClient and MCPRegistry

### ✅ DONE — Slash commands: /create-persona, /create-mcp, /create-agent, /run-agent
- `POST /api/personas` endpoint + `createPersona` in api.ts
- `POST /api/agents` + `DELETE /api/agents/{slug}` + `GET /api/agents`
- All four commands use step-by-step wizard UI (one question at a time, Enter to advance)
- `/run-agent <slug>` prompts for task then sends `spawn_agent` WS message

### ✅ DONE — Subagent system
- `backend/subagent.py`: `SubAgentRunner` (asyncio Task per subagent, restricted tool registry, max_turns + timeout caps, cancellable via `kill()`)
- `AgentSupervisor` per WebSocket connection: `spawn()`, `kill()`, `kill_all()` on disconnect
- WS protocol: `spawn_agent`, `kill_agent`, `list_agents_running`, `get_agent_log` (inbound); `agent_spawned`, `agent_token`, `agent_tool_call`, `agent_tool_result`, `agent_final`, `agent_error`, `agent_status`, `agent_killed` (outbound)
- Safety: subagents get only the tool subset listed in their profile; parent kills all on WS disconnect
- Agent profiles stored in `backend/agents/<slug>.md` with frontmatter

### ✅ DONE — AgentsPanel
- `frontend/src/components/AgentsPanel.tsx`: "agents" tab in right panel
- Shows active runners (with Kill button), recent finished, and all saved profiles
- Inline log drawer: real-time streaming of tool calls, tokens, results — toggle with "Log" button
- "agents" tab added to both desktop header and mobile sub-tabs

### ✅ DONE — Linux packaging + Ollama auto-start
- `build-linux.sh`: builds frontend, installs Python deps to venv, assembles AppDir, downloads `appimagetool`, produces `dist/OpenCowork-x86_64.AppImage` and `dist/opencowork_<version>_amd64.deb`
- `opencowork.desktop`: KDE/GNOME desktop entry (Categories: Utility;Development;ArtificialIntelligence)
- Auto-start Ollama in `run()` if binary is present and port 11434 is not yet listening
- Port auto-fallback: scans from 7337 upward, prints the actual URL on startup

### 📋 TODO — Remaining
- [ ] Wire `MCPRegistry` into `lifespan` in `main.py`
- [ ] Tests for subagent system and agent profile CRUD
- [ ] Frontend tests for new slash command wizards
- [ ] `PersonaPicker` should use `api.writeConfig` instead of raw fetch
