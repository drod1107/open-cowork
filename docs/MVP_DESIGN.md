# OpenCowork MVP Design Specification

Living document — updated as decisions are made. All opencode chats should check this file first for agreed-upon context.

## Core Purpose

A personal local-first AI co-working agent that runs on your desktop, accessible via a mobile-optimized web UI over Tailscale. The web UI acts as a "tunnel" to the desktop, letting you use desktop GPU/CPU power for coding, research, and work on the go without third-party services. No Android app — the web UI is the only client.

## MVP Scope (Phase 1 — COMPLETE)

### What's In
- **Backend**: Python/FastAPI + WebSockets, chat streaming with model providers (Ollama/OpenAI-compatible), *only shell tool*
- **Frontend**: React/TypeScript/Vite/Tailwind, 3-tab mobile UI (Chat, History, Settings)
- **Session History**: Persistent SQLite sessions, resumable conversations
- **Context Awareness**: History injection, num_ctx maximization, spillover, read_chunk, compaction, token estimation
- **Tech Stack**: Python 3.11+, FastAPI, SQLite, TOML config, React 18+, TypeScript, Vite, Tailwind CSS
- **Deployment**: Single `./run.sh` command starts server on `:7337`, serves compiled frontend dist
- **Ollama auto-start**: If Ollama binary exists and port 11434 not in use, backend auto-starts it
- **Port auto-fallback**: Scans upward from 7337 if port is taken, prints actual URL on startup
- **Provider Support**: Ollama, LM Studio, vLLM, SGLang, NVIDIA API (OpenAI-compatible)
- **Security**: Tailscale-only access, no additional auth, permission gate for tool calls
- **Kill-Switch**: Stop kills stream AND any running shell PIDs via SIGTERM-first, then SIGKILL

### What's Out (Future Phases)
- Personas system (Phase 3)
- Skills system (Phase 2)
- Subagents (Phase 3)
- MCP server integration (Phase 2)
- Web/browser/computer/coding tools (various phases)
- Scheduler (future)
- Desktop-optimized UI (future)

## WebSocket Protocol (MVP)

### Client → Server
- `chat`: send message + session_id
- `stop`: cancel stream + kill shell PIDs
- `permission_response`: user's choice ("this time" / "always" / "no" / "never")

### Server → Client
- `token`: streaming text chunk
- `final`: complete response
- `tool_call`: shell command being run
- `tool_result`: command output
- `permission_request`: popup in chat stream
- `error`: something went wrong
- `session_id`: new session created

## Config.toml MVP Structure

- Supports **multiple providers** stored in config (not just active one)
- Fields per provider: `provider` (ollama/lmstudio/vllm/sglang/custom), `base_url`, `nickname` (optional human-friendly name), tool toggles (boolean), permission toggles (per-command booleans), blocked list
- `working_dir`: global setting (config exists, UI in Phase 2)
- Active provider tracked separately

```toml
provider = "ollama"
base_url = "http://localhost:11434"

[tools]
shell = true

[permissions.shell]
allowed_commands = ["ls*", "pwd", "echo*", "cat*", "grep", "git status", "git diff*"]
blocked_commands = ["rm -rf /*", "mkfs*", "dd if=*", ":(){:|:&};:"]
```

## NVIDIA API Configuration (Secure)

- **Credentials stored in `.env` file** (never in config.toml or codebase)
- Backend reads from environment using `os.getenv("NVIDIA_API_KEY")` — never hardcode credentials
- **`.env` must be in `.gitignore`** to prevent accidental commits
- **Popup consent flow:** Backend tracks user consent state in memory (not persisted). If user declines, suppress all pings to NVIDIA until user manually selects it.

### Provider Ping Behavior
- Ping providers **only when**: app first opens, user updates a provider config, user opens provider dropdown/model picker
- **Not** constant polling
- Ping result green = provider active in dropdown, selectable
- Ping result fails = provider greyed out + "Disconnected" label in dropdown
- Error message from failed ping shown under provider name in Settings for user to debug connection

## Security Model

- **Tailscale-only access**: No built-in authentication. App is unreachable without Tailscale network auth.
- **Instant access**: Stored Tailscale auth grants access without additional sign-on.
- **Tool permission gate**: All tool calls gated by per-command boolean flags (MVP) — toggles in UI map to backend enforcement of allowed/blocked commands.
- **PermissionGate check order**: (0) toggle check → (1) allowlist → (2) blocklist → (3) default → (4) prompt user

## UI Design (Mobile-First)

### Tab 1: Chat (Primary Workspace)
- **Top bar:** Session ID displayed (Phase 2: click-to-edit human-readable name). **Model picker dropdown** to select from provider's advertised models.
- **Chat area:** Scrollable message display, inline tool call output (full command + output, no collapse in MVP)
- **Input area:** Textarea (not single-line), far-left plus button → "Select a project folder"
- **Send/Stop button:** 1/2 height of chat input box, converts to "Stop" after message sent, stays until full response completes. Stop kills stream AND any running shell PIDs via SIGTERM-first then SIGKILL.
- **Debug icon:** Bottom right, underneath send/stop button, 1/4 height of input box. Opens debug bar above input box (red, high-contrast text). Copy button at far left. Copies ALL debug output to clipboard.
- **Permission Request Popup:** Appears inline in chat stream with 4 tappable options: "This time", "Always", "No", "Never". After selection, box shrinks to log entry. Chat continues streaming.

### Tab 2: History
- Chronological session list (title + timestamp)
- Tap to resume: switches to Chat tab, loads session history
- Delete (swipe or long-press)
- No search/filter (future)

### Tab 3: Settings (3 Subsections)

#### Model Providers
- Dropdown with 4 presets (Ollama, LM Studio, vLLM, SGLang) with default base_urls auto-filled
- **NVIDIA API (default remote fallback):** Always available, but only connects after explicit user consent via popup
- Editable fields (change port, use Tailscale URL, etc.)
- Plus button in Settings > Model Providers subsection (Phase 2): opens popup form with provider type dropdown (Ollama, LM Studio, vLLM, SGLang, NVIDIA, Custom). Known providers pre-populate default base_url; Custom opens blank form.
- Provider ping: only when app opens, user updates config, or opens dropdown
- Multiple providers stored in config.toml, persists across restarts

#### Tools
- List only shell/bash tool, with **slide toggle** to enable/disable model's access to the tool
- Backend enforces tool-level block when toggled off

#### Permissions
- List grouped by tool (shell only for MVP), per-command **slide toggles**
- **Blocked List:** Section showing permanently denied permissions. Plus button → form. Click existing entry → popup to reset.
- **Permission Request Popup options:** "This time", "Always", "No", "Never". "Always" writes to config.toml. "Never" adds to blocked list.

### Mobile-First Principles
- **Bottom tab bar**: Anchored, no dead space, fixed position, scrollable content above
- **Layout**: Strictly single-column, full width of screen
- **Priority**: Mobile portrait phone experience is primary, desktop UI is incidental

## Agreed Decisions Log
- MVP scope: chat + streaming + shell tool only, 3-tab mobile UI
- Cut personas, skills, subagents, MCP for Phase 1
- Session history required for MVP
- Mobile is primary purpose, desktop UI incidental
- Tailscale-only auth, no additional sign-on
- Bottom tab bar: anchored, no dead space, fixed position
- Skip session title edit for MVP (Phase 2)
- Tool call output inline full display (no collapse) for MVP
- Strictly single-column full width layout for MVP
- Scheduler was AI-hallucinated feature — cut from MVP, future phase
- Tool toggle OFF → CANNOT BE USED EVER (overrides permanent approvals)
- Tool toggle ON → CAN use permanently allowed, CAN request non-approved, CANNOT do permanently disallowed
- HubState fields: provider, permission_gate, active_agent, active_pid, stop_event, connections (no scheduler)
