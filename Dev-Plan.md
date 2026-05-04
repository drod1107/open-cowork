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
- Scheduled AI tasks (cron-for-AI via APScheduler)

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
- Plus button in Settings > Model Providers subsection: opens popup form with provider type dropdown (Ollama, LM Studio, vLLM, SGLang, NVIDIA, Custom). Known providers pre-populate default base_url; Custom opens blank form. API key field optional (for NVIDIA/Custom). This is the ONLY way to add providers — no text box clutter in main UI.
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

## Context Awareness System (Agent Memory)

### Problem

The agent has **zero memory** across messages. Every call to `agent.run_stream()` builds the message list from scratch with only the system prompt and the current user message. Session history is faithfully stored in SQLite but never read back. The model itself confirmed this in UAT: *"I do not have memory of previous messages or interactions. Each message is processed independently."*

### Architecture: Virtual Memory for LLMs

The design follows the same principles as a virtual memory system:

| Concept | OS Analogy | Our Implementation |
|---------|-----------|-------------------|
| Context window | RAM | The model's `num_ctx` token limit (limited, fast) |
| Spillover storage | Disk | SQLite records or temp files for large tool output |
| Compaction | Garbage collection | Summarize old turns into a compact summary message |
| Paging | Page fault → disk read | `read_chunk` tool lets the model page through saved output on demand |

**Core principle: never truncate, never lose data.** If a tool result is the length of War and Peace, it gets saved as a "book" — not read verbatim into context. The model reads it one chapter at a time, distilling understanding as it goes, without ever overwhelming context.

### Components

#### 1. History Injection (Critical Path)

**Current:** `agent.run_stream(user_message)` sends only `[system, user_message]` to the LLM.

**Fix:** Load session history from SQLite before each call. Convert stored messages to OpenAI format. Prepend to the messages list:

```
[system_prompt, ...history_messages, current_user_message]
```

- `_build_history(session_id)` — new function in `main.py` that calls `get_session()`, converts stored messages to OpenAI `messages` format
- `Agent.run_stream()` — accept optional `history: list[dict]` parameter, prepend before current message
- Tool-call/result pairs must be reconstructed in OpenAI format (`assistant` with `tool_calls` → `tool` role with `tool_call_id`)

#### 2. Tool Result Spillover (No Truncation)

**Current:** Shell output is stuffed directly into the tool result message. A `find /` could blow the entire context window.

**Fix:** When tool output exceeds a configurable threshold (default 4KB), write it to a spillover record and store a reference instead:

- In context: `[Shell output: 47KB, saved to spillover abc123. Use read_chunk to access.]`
- On disk: `backend/db/spillover/abc123.txt` (or a `spillover` SQLite table)
- The `read_chunk(file_id, offset, limit)` tool lets the model page through the output in manageable pieces
- System prompt tells the agent: *"When you see [Output saved as spillover abc123, 47KB], use read_chunk to read it in pieces. Read, understand, summarize, then read the next chunk."*
- Spillover files are cleaned up when the session is deleted or after a configurable TTL

#### 3. Context Compaction (Garbage Collection)

**Current:** No limit on context size. Long conversations will exceed the model's window and fail.

**Fix:** When the message history exceeds a token budget (default 75% of `num_ctx`), compact the oldest messages:

1. Take all messages before the last N turns (keep recent context intact)
2. Send them to a compactor call (same model, or configurable smaller/faster model)
3. Replace those messages with a single system message: `[Previous conversation summary: <summary>]`
4. The session DB retains the ORIGINAL messages — compaction is a runtime optimization, not data destruction
5. Compaction runs proactively before each LLM call when budget is exceeded
6. Tool-call/result pairs are always kept together in the compaction boundary

**Compaction trigger flow:**
```
User sends message
  → Load full history from session
  → Estimate token count (len(text) / 4 heuristic, or tiktoken if available)
  → If tokens > budget:
      → Extract old messages (everything before last 2 turns)
      → LLM call: "Summarize this conversation so far, preserving key facts, decisions, and tool results"
      → Replace old messages with summary
  → Run agent with compacted context
```

#### 4. num_ctx Maximization

**Current:** Ollama uses its default `num_ctx` (often 2048-4096 tokens). Models can handle much more.

**Fix:** 
- Set `num_ctx` to a configurable value (default 8192 for 8B models, 32768 for larger)
- Pass via `extra_body={"options": {"num_ctx": N}}` in the OpenAI client call (Ollama /v1 endpoint)
- Only applied for Ollama provider (other providers manage their own context)
- Add `context_window` setting to `config.toml` under `[agent]`
- The value should be set to the model's maximum supported context, not a conservative default

#### 5. Smart Token Budgeting

**Current:** No concept of token budgets at all.

**Fix:**
- `agent.max_context_tokens` — configurable, default from config
- `_estimate_tokens(messages)` — rough count: sum of `len(content) / 4` for all messages
- Budget allocation:
  - System prompt: ~10% of window
  - Compaction summary: ~10% 
  - Recent turns (last 2-3): ~30%
  - Tool results + current message: ~50%
- If any single tool result would exceed the remaining budget → spillover

### Config.toml Additions

```toml
[agent]
context_window = 8192          # num_ctx for Ollama, ignored for other providers
compaction_threshold = 0.75    # compact when 75% of context_window is used
spillover_threshold = 4096     # bytes; tool outputs larger than this go to spillover
spillover_ttl_hours = 24       # clean up spillover files after this long
```

### Implementation Order

1. **History injection** — The critical missing piece. Without this, the agent is useless for any multi-turn conversation. Load session messages → pass to agent → model has context.
2. **num_ctx maximization** — Must be set high enough to actually hold the history we're now injecting. These two are co-dependent.
3. **Tool result spillover** — Once we have history injection, long tool outputs become a problem. Spillover prevents context overflow from large outputs.
4. **read_chunk tool** — The model needs a way to access spillover data. New tool that reads a chunk of a saved output.
5. **Context compaction** — The final piece. Long conversations will eventually exceed even a large context window. Compaction keeps things manageable indefinitely.
6. **Smart token budgeting** — Refinement of the compaction trigger. More precise budget allocation.

### Design Decisions

- **Session DB stores originals, compaction is runtime-only** — Never destroy the raw conversation data. Compaction is an optimization for the LLM call, not a modification of the source of truth.
- **Spillover is opt-in per tool result** — Only outputs exceeding the threshold get spilled. Small outputs stay inline in context where they're immediately available.
- **Compaction preserves tool pairs** — Never split a tool_call from its tool_result. If the boundary falls in the middle of a tool interaction, expand the compaction region to include the complete pair.
- **read_chunk is a real tool** — The model decides when to use it, just like shell. It appears in the tool list alongside shell. The model can read multiple chunks sequentially, building understanding incrementally.
- **No summarization of spillover content** — The model reads the raw data. If it wants a summary, it can write one itself using the shell tool or in its response. We don't auto-summarize because we can't know which details matter.

### Out of Scope for This Feature

- RAG/vector embeddings for context retrieval
- Multi-model compaction (using a smaller model to summarize)
- Semantic search across session history
- Cross-session context sharing

---

## Phase 2: Scheduled AI Tasks (Cron-for-AI)

### Concept

Your AI coworker can do things on a timer, not just when you chat. Schedule the agent to run tasks on cron schedules — e.g., "every morning at 7am, check if my tests pass and summarize results," or "every Monday, generate a weekly summary of git commits."

### Engine

[APScheduler](https://github.com/agronholm/apscheduler) (MIT, 7.5k stars) — mature Python task scheduler with:
- Cron-style, interval, and one-off triggers
- Persistent job storage (SQLite, PostgreSQL, MongoDB) — jobs survive restarts
- Native asyncio support — fits FastAPI's async model
- Multi-node scaling if needed later

### User Stories

1. **Create a scheduled task** — User types a natural-language description and a cron schedule. The agent runs that description as a prompt on schedule.
2. **View scheduled tasks** — List all jobs with their schedule, next run time, and last result.
3. **Delete a scheduled task** — Remove a job from the schedule.
4. **View task run log** — See when scheduled tasks fired, succeeded, or failed.
5. **Receive results** — When a scheduled task completes, its output appears in the chat as a system message (or notification).

### Backend Spec (To Be Written by Dev When Phase 2 Starts)

- `Scheduler` class wrapping APScheduler with cron-only API
- REST endpoints: `GET/POST/DELETE /api/schedules`
- WebSocket events: `scheduler_start`, `scheduler_event`, `scheduler_end`, `scheduler_error`
- Job storage in `sessions.db` via SQLAlchemyJobStore
- `_task_runner` function: builds a fresh agent, runs the description, broadcasts events

### Frontend Spec (To Be Written When Phase 2 Starts)

- New "Schedule" section in Settings tab (or its own tab)
- Form: natural-language description + cron expression + optional job ID
- Job list with schedule, next run, status
- Run log with timestamps and outcomes
- Scheduled task results surface in Chat tab

### Status

Not started. Infrastructure removed from MVP (scheduler.py, endpoints, APScheduler dependency). Will be re-implemented from this spec when Phase 2 begins.

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
- [2026-05-03] Added Context Awareness System design (history injection, spillover, compaction, num_ctx, read_chunk)
- [2026-05-03] Stripped scheduler from MVP — hallucinated feature with no spec. Moved to Phase 2 as "Scheduled AI Tasks"
