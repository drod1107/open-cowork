# OpenCowork MVP Development Plan

## Project Overview

**Goal:** Build a mobile-first, local-first AI co-working agent that runs on desktop hardware and is accessible via a mobile-optimized web UI over Tailscale. The web UI acts as a "tunnel" to desktop GPU/CPU power for coding, research, and work on the go without third-party services.

**Approach:** 100% BDD/TDD. Write real E2E tests first, then code to pass. One feature at a time. No fake/mocked tests — only tests that prove real user-facing behavior.

**Branches:**
- `dev` — Clean MVP baseline (force-pushed, stripped of out-of-scope code)
- `mvp/features` — Active development branch (all MVP work happens here)

---

## MVP Scope (Phase 1)

### What's In
- **Backend:** Python/FastAPI + WebSockets, chat streaming with model providers (Ollama/OpenAI-compatible), **only shell tool**
- **Frontend:** React/TypeScript/Vite/Tailwind, **3-tab mobile UI** (Chat, History, Settings)
- **Session History:** Persistent SQLite sessions, resumable conversations
- **Tech Stack:** Python 3.11+, FastAPI, SQLite, TOML config, React 18+, TypeScript, Vite, Tailwind CSS
- **Deployment:** Single `./run.sh` command starts server on `:7337`, serves compiled frontend dist
- **Provider Support:** Ollama, LM Studio, vLLM, SGLang (with custom provider option)
- **NVIDIA API:** Default remote fallback provider (DeepSeek v4 Pro via NVIDIA integrate.api.nvidia.com), credentials stored securely in `.env`, only connects after explicit user consent via popup
- **Security:** Tailscale-only access, no additional auth, permission gate for tool calls

### What's Out (Planned for Later Phases)
- Personas system
- Skills system
- Subagents
- MCP server integration
- Web/browser/computer/coding tools (beyond shell)
- Desktop-optimized UI (incidental, mobile is primary)

---

## UI Design (Mobile-First)

### Tab 1: Chat (Primary Workspace)
- **Top bar:** Session ID (Phase 2: editable title), Model picker dropdown (populated from provider's advertised models)
- **Chat area:** Scrollable message display, inline tool call output (full command + output, no collapse in MVP)
- **Input area:** Textarea (not single-line), far-left plus button → "Select a project folder" (opens folder picker on local machine, filters to folders only)
- **Send/Stop button:** 1/2 height of chat input box, converts to "Stop" after message sent, stays until full response (including tool calls) completes. Stop kills stream AND any running shell PIDs via SIGKILL.
- **Debug icon:** Bottom right, underneath send/stop button, 1/4 height of input box. No button chrome, just icon. Opens debug bar above input box (red, high-contrast text). Copy button at far left (doesn't overlap text). Copies ALL debug output to clipboard.

### Tab 2: History
- **Session list:** Chronological, shows title + timestamp
- **Tap:** Resume session (switches to Chat tab, loads history)
- **Long press:** Context menu with "Delete" → confirmation popup ("Delete this chat permanently? Y/N")
- Delete removes from storage, not logs (backend note: sessions table only)

### Tab 3: Settings (3 Subsections)

#### Model Providers
- Dropdown with 4 presets (Ollama, LM Studio, vLLM, SGLang) with default base_urls auto-filled
- **NVIDIA API (default remote fallback):** Always available in provider list, but:
  - App defaults to local providers first (starting with Ollama if running)
  - On first app load, if no local providers are available, fires a **popup**: "No local providers detected. Connect to NVIDIA API (DeepSeek v4 Pro) as fallback? [Yes] [No]"
  - If user clicks "Yes": ping NVIDIA API using credentials from `.env`, if successful → models appear in model picker
  - If user clicks "No": NO ping ever sent to NVIDIA unless user manually tries to select it from provider dropdown again
  - If "No" was selected, provider appears greyed out with "Disconnected" and note: "User declined connection"
- Editable fields (change port, use Tailscale URL, etc.)
- Plus button for custom provider form: text inputs for all required fields, greyed-out tooltips as placeholders, no defaults
- Provider ping: only when app opens (for local providers), user updates config, or opens dropdown. Green = active, Greyed out + "Disconnected" = failed. Error message shown under provider name.
- Multiple providers stored in config.toml, persists across restarts

#### Tools
- List only shell/bash tool, with **slide toggle** to enable/disable model's access to the tool
- Backend enforces tool-level block when toggled off

#### Permissions
- List grouped by tool (shell only for MVP), per-command **slide toggles** (initial list: `ls`, `pwd`, `echo`, `cat`, `grep`, `git status`, `git diff`)
- Backend enforces: disabled = blocked, enabled = allowed
- **Blocked List:** Section showing permanently denied permissions. Plus button → dropdown (tool) + text field (command). Click existing entry → popup: "Reset this permission? Renews model's ability to request this permission (does not grant it)."

#### Permission Request Popup (appears inline in Chat tab)
- Options: "This time", "Always", "No", "Never"
- "Always" = writes to config.toml as perpetually granted
- "Never" = added to blocked list in config.toml
- After selection, box shrinks to log entry showing request + user's choice
- Chat continues streaming

---

## Backend Architecture

### WebSocket Protocol (MVP)
**Client → Server:**
- `chat` (send message + session_id)
- `stop` (cancel stream + kill shell PIDs)
- `permission_response` (user's choice)

**Server → Client:**
- `token` (streaming text chunk)
- `final` (complete response)
- `tool_call` (shell command being run)
- `tool_result` (command output)
- `permission_request` (popup in chat stream)
- `error` (something went wrong)
- `session_id` (new session created)

### Config.toml MVP Structure
```toml
provider = "ollama"
base_url = "http://localhost:11434"

[tools]
shell = true

[permissions.shell]
allowed_commands = ["ls*", "pwd", "echo*", "cat*", "grep", "git status", "git diff*"]
blocked_commands = ["rm -rf /*", "mkfs*", "dd if=*", ":(){:|:&};:"]
```

### NVIDIA API Configuration (Secure)
- **Credentials stored in `.env` file** (never in config.toml or codebase):
  ```
  NVIDIA_API_KEY=REDACTED
  NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
  NVIDIA_MODEL=deepseek-ai/deepseek-v4-pro
  ```
- **Backend reads from environment** using `os.getenv("NVIDIA_API_KEY")` — never hardcode credentials
- **`.env` must be in `.gitignore`** to prevent accidental commits
- **API usage (from backend):**
  ```python
  from openai import OpenAI
  
  client = OpenAI(
    base_url=os.getenv("NVIDIA_BASE_URL"),
    api_key=os.getenv("NVIDIA_API_KEY")
  )
  
  completion = client.chat.completions.create(
    model=os.getenv("NVIDIA_MODEL", "deepseek-ai/deepseek-v4-pro"),
    messages=[{"role": "user", "content": user_text}],
    temperature=1,
    top_p=0.95,
    max_tokens=16384,
    extra_body={"chat_template_kwargs": {"thinking": False}},
    stream=True
  )
  ```
- **Popup consent flow:** Backend tracks user consent state in memory (not persisted). If user declines, suppress all pings to NVIDIA until user manually selects it.

### Database Schema
- `sessions` table: `(id TEXT PK, created_at, updated_at, messages JSON, metadata JSON)`
- `apscheduler_jobs` table: owned by APScheduler (do not touch)

### Kill-Switch Mechanism
- Backend stores shell PIDs in `HubState._current_shell_pids` during tool execution
- `stop` message triggers `HubState.stop_current()`:
  1. Kills all stored PIDs via `os.kill(pid, SIGKILL)`
  2. Cancels the agent's asyncio task
- **Extensibility note:** Pattern must be written so any dev can extend to other tool types (e.g., web tool = kill browser session, interrupt response delivery).

### Provider Ping Behavior
- **Local providers (Ollama, LM Studio, vLLM, SGLang):** Pings only when app first opens, user updates config, or opens dropdown
- **NVIDIA API (remote fallback):**
  - On app start: only ping if user previously consented (tracked in backend memory)
  - If no local providers detected AND user hasn't declined NVIDIA: show popup asking for consent
  - If user clicks "Yes": ping NVIDIA, populate models if successful
  - If user clicks "No": NEVER ping NVIDIA again unless user manually selects it from dropdown
  - If "No" was selected: provider greyed out in dropdown with "User declined connection"
- NOT constant polling for any provider
- Green = provider active in dropdown, selectable
- Failed = provider greyed out + "Disconnected" label + error message shown

---

## Development Workflow

### Phase 1: Establish Clean Baseline ✅ (COMPLETE)
1. ✅ Started with `faa9c79` as baseline (working-branch tip)
2. ✅ Removed all fake/mocked tests (test_agent.py, test_main_api.py)
3. ✅ Removed out-of-scope code (personas, skills, subagents, MCP, web/browser/computer/coding tools)
4. ✅ Simplified config.toml to shell-only + boolean toggles
5. ✅ Rewrote frontend components to MVP 3-tab mobile layout
6. ✅ Added stop/kill-switch to main.py
7. ✅ 20/20 backend tests pass
8. ✅ Pushed clean baseline to `dev` (force push)
9. ✅ Created `mvp/features` branch for MVP work

### Phase 2: Write Complete E2E Test Suite (CURRENT PHASE)
1. **Create comprehensive test list** covering ALL MVP functionality:
   - Real WebSocket chat flow (send message → receive streaming tokens → receive final)
   - Real shell command execution through full agent→tool→permission stack
   - Permission request → user response → tool execution flow
   - Session creation, persistence to SQLite, resume from History tab
   - Stop button kills stream + shell PIDs
   - Model picker populated from provider's advertised models
   - Provider ping behavior (green/grey states)
   - **NVIDIA API integration:**
     - `.env` file properly configured with credentials (not in codebase)
     - Backend reads credentials via `os.getenv()` (no hardcoded keys)
     - Popup consent flow: shows when no local providers + user hasn't declined
     - "Yes" → pings NVIDIA, populates model list on success
     - "No" → never pings NVIDIA unless user manually selects it
     - NVIDIA provider greyed out with "User declined connection" after "No"
   - Settings: tool toggle on/off, permission toggles, blocked list management
   - Config persistence across restarts
   - Ollama auto-start and port auto-fallback

2. **Review tests** with second model (team ate mode)
   - One model writes tests
   - Other model reviews for coverage gaps
   - Both models agree on completeness

3. **Division of labor:**
   - Model A writes feature X + tests
   - Model B reviews Model A's code
   - Model B writes feature Y + tests
   - Model A reviews Model B's code
   - Continue in tandem until Phase 1 MVP is complete

### Phase 3: Implement Features to Pass Tests
- One feature at a time: write code → pass tests → commit atomically
- No new features until all MVP tests pass
- All changes committed atomically with clear messages

### Phase 4: Build, Serve, Manual E2E Verification
- Frontend builds successfully (`cd frontend && npm run build`)
- Backend starts successfully (`./run.sh`)
- App serves on `:7337`
- Manual testing on mobile device over Tailscale matches all MVP requirements

---

## Team Collaboration Protocol

### Pair Programming with Team ate Mode
- **User (David):** PM/Interface, defines requirements, reviews progress
- **Model A (opencode/big-pickle):** Feature implementation, test writing, code review
- **Model B (Claude in teammate-mode):** Test writing, code review, feature implementation

### Workflow
1. **Test Planning:** Model A creates `Dev-Plan.md` (this document), Model B creates comprehensive test list
2. **Test Review:** Both models review test coverage, agree on completeness
3. **Division:** Split features between models, one writes → other reviews
4. **Integration:** All code merged to `mvp/features`, tested together
5. **Verification:** Build, serve, manual E2E on mobile device
6. **Phase 2:** After MVP complete, repeat process for next phase (additional tools, personas, skills, etc.)

---

## MVP Feature Checklist (For Test Writing)

### Backend
- [ ] WebSocket chat flow (real Ollama/provider connection)
- [ ] Shell tool execution with permission gate
- [ ] Permission request → user response → tool execution
- [ ] Stop button kills stream + shell PIDs (kill-switch)
- [ ] Session creation and persistence to SQLite
- [ ] Session resume from History
- [ ] Config.toml read/write (tools, permissions, providers)
- [ ] Provider ping and model list population
- [ ] **NVIDIA API integration:**
  - [ ] `.env` file created with credentials (API key, base URL, model)
  - [ ] Backend reads NVIDIA credentials via `os.getenv()` (secure, no hardcoded keys)
  - [ ] `.env` added to `.gitignore` (prevent accidental commits)
  - [ ] Popup consent flow: detect no local providers → ask user "Connect to NVIDIA API?" 
  - [ ] "Yes" → ping NVIDIA API, populate model picker on success
  - [ ] "No" → suppress all future NVIDIA pings unless user manually selects it
  - [ ] Track user consent state in backend memory (not persisted)
  - [ ] NVIDIA provider greyed out with "User declined connection" after "No"
  - [ ] Streaming works with NVIDIA API (DeepSeek v4 Pro)
- [ ] Ollama auto-start (if binary exists, port 11434 free)
- [ ] Port auto-fallback (scans from 7337 upward)
- [ ] Multiple provider storage and switching (including NVIDIA)
- [ ] Tool toggle (shell on/off) enforcement
- [ ] Permission toggle (per-command boolean) enforcement
- [ ] Blocked list management (add/remove/reset)

### Frontend
- [ ] 3-tab mobile layout (Chat, History, Settings)
- [ ] Bottom tab bar (fixed, no dead space, no content cut off)
- [ ] Chat tab: textarea input, send/stop button, debug icon/bar
- [ ] Chat tab: inline tool call output (full display)
- [ ] Chat tab: permission request popup with 4 options
- [ ] Chat tab: model picker dropdown (populated from provider)
- [ ] History tab: chronological session list
- [ ] History tab: tap to resume (switches to Chat tab)
- [ ] History tab: long press → delete with confirmation
- [ ] Settings tab: Model Providers subsection (dropdown, presets, custom)
- [ ] Settings tab: NVIDIA API as fallback provider with popup consent flow
- [ ] Settings tab: Tools subsection (shell toggle)
- [ ] Settings tab: Permissions subsection (per-command toggles, blocked list)
- [ ] Settings tab: provider ping behavior (green/grey states)
- [ ] Debug bar: copy all output to clipboard
- [ ] Config persistence across restarts

---

## Extensibility Notes (For Future Phases)

### Kill-Switch Pattern
When extending to other tool types (web, browser, computer, coding), follow the pattern:
- Each tool stores relevant PIDs/process identifiers in `HubState`
- `stop_current()` iterates through all stored IDs and kills them appropriately
- Document the kill method for each tool type (SIGKILL for shell, browser session terminate for Playwright, etc.)

### Permission System
Current: Per-command boolean toggles (MVP)
Future: Extend to support "ask/allow/deny" modes, pattern matching (fnmatch), per-session ephemeral dirs

### Mobile-First Principles
- Strictly single-column, full width for MVP
- Phase 2: Multi-column/responsive for tablets, landscape, desktop
- Phase 2: Session title inline editing, collapsible tool call components

---

## Current Status

**Branch:** `mvp/features` (clean baseline established)
**Next Step:** Model B (Claude teammate-mode) to create comprehensive E2E test list covering all MVP functionality listed above
**Test Review:** Both models agree on test coverage completeness
**Then:** Begin division of labor, implement features one at a time, review each other's code

---

## Change Log

- [2026-05-02] Established MVP design via conversation with user (all decisions logged in MVP_DESIGN.md)
- [2026-05-02] Created `cleanup-baseline` branch from `faa9c79`
- [2026-05-02] Stripped fake tests and out-of-scope code
- [2026-05-02] Rewrote frontend to MVP 3-tab mobile layout
- [2026-05-02] Added stop/kill-switch to backend
- [2026-05-02] Pushed clean baseline to `dev` (force push)
- [2026-05-02] Created `mvp/features` branch
- [2026-05-02] Created `Dev-Plan.md` for team collaboration
- [2026-05-02] Added NVIDIA API as default remote fallback provider (DeepSeek v4 Pro via integrate.api.nvidia.com)
- [2026-05-02] Credentials stored securely in `.env` (NVIDIA_API_KEY, NVIDIA_BASE_URL, NVIDIA_MODEL)
- [2026-05-02] Backend to read credentials via `os.getenv()` — no hardcoded keys
- [2026-05-02] Default to local providers first (Ollama), NVIDIA only after popup consent
- [2026-05-02] Popup flow: "No local providers detected. Connect to NVIDIA API? [Yes] [No]"
- [2026-05-02] "No" = never ping NVIDIA unless user manually selects it from dropdown
- [2026-05-02] Updated all relevant sections: MVP Scope, UI Design, Backend Architecture, Test Checklist
