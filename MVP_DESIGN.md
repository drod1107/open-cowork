# OpenCowork MVP Design Specification
*Living document — updated as decisions are made. All opencode chats should check this file first for agreed-upon context.*

## Core Purpose
A personal local-first AI co-working agent that runs on your desktop, accessible via a mobile-optimized web UI over Tailscale. The web UI acts as a "tunnel" to the desktop, letting you use desktop GPU/CPU power for coding, research, and work on the go without third-party services. No Android app — the web UI is the only client.

## MVP Scope (Phase 1 POC)
### What's In
- **Backend**: Python/FastAPI + WebSockets, chat streaming with model providers (Ollama/OpenAI-compatible), *only shell tool* (other tools: web, browser, computer, coding cut for now)
- **Frontend**: React/TypeScript/Vite/Tailwind, 3-tab mobile UI (Chat, History, Settings)
- **Session History**: Persistent SQLite sessions, resumable conversations
- **Tech Stack**: Python 3.11+, FastAPI, SQLite, TOML config, React 18+, TypeScript, Vite, Tailwind CSS
- **Deployment**: Single `./run.sh` command starts server on `:7337`, serves compiled frontend dist (no separate frontend runtime)
- **Ollama auto-start**: If Ollama binary exists and port 11434 not in use, backend auto-starts it
- **Port auto-fallback**: Scans upward from 7337 if port is taken, prints actual URL on startup
- **Provider Support**: Ollama, LM Studio, vLLM, SGLang

### What's Out (Planned for Later Phases)
- Personas system
- Skills system
- Subagents
- MCP server integration
- Web/browser/computer/coding tools (beyond shell)
- Desktop-optimized UI (incidental, mobile is primary)

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
- `working_dir`: global setting
- Active provider tracked separately

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

## UI Design (Mobile-First)
### Tab Structure
1. **Chat Tab** (primary workspace)
   - Streaming message display with inline tool call output (full command + output, no collapse)
   - Pinned input bar at bottom (above tab bar)
   - **Input box**: text field (not single-line bar) for easy mobile editing. Far-left: plus button → dropdown with "Select a project folder" (opens folder picker on local machine running the app; filters to folders only). Later Phase 2: "Attach a file", "Add a connection".
   - **Send/Stop button**: 1/2 height of chat input box, sits to right of input box. Converts to stop button after message sent, stays until full response (including tool calls) completes. Stop kills stream AND any running shell PIDs via SIGKILL.
   - **Debug icon**: bottom right, underneath send/stop button. 1/4 height of chat input box. No visible button chrome, just icon. Spaced with gaps above/between/below so not smushed. Click opens **Debug Bar** (red, high-contrast text) mounted above input box, below chat history. Copy button at far left (doesn't overlap text). Copies ALL debug output to clipboard. Debug bar shows CLI error outputs from frontend/backend.
   - **Top bar**: chat session ID displayed (Phase 2: becomes click-to-edit human-readable name). **Model picker dropdown** to select from provider's advertised models.
   - **Permission Request Popup**: Appears inline in the chat stream (above chat input box, above debug bar if open). Shows tool call request with 4 tappable options: "This time", "Always", "No", "Never". After user taps one, box shrinks to a log entry showing request + user's choice. Chat continues streaming (if approved: tool runs → output inline → model replies).
   - No session title editing (Phase 2)

2. **History Tab** (session management)
   - Chronological session list (title + timestamp)
   - Tap to resume: switches to Chat tab, loads session history
   - Delete (swipe or long-press)
   - No search/filter (Phase 2)

3. **Settings Tab** (3 subsections)
   - **Model Providers**: Dropdown with 4 presets (Ollama, LM Studio, vLLM, SGLang) with default base_urls auto-filled. User can edit any default field (e.g., change port, use Tailscale URL). Plus button opens custom provider form: text inputs for all required fields (provider nickname, base_url without /v1, etc.) with greyed-out tooltips as placeholders, no defaults. Selecting a preset instantly connects and populates model picker with that provider's advertised models.
   - **Tools**: List only shell/bash tool, with slide toggle to enable/disable model access to the tool (backend enforces tool-level block)
   - **Permissions**: List grouped by tool (shell only for MVP), per-command boolean toggles via slide toggle (initial list: `ls`, `pwd`, `echo`, `cat`, `grep`, `git status`, `git diff`). Backend enforces: disabled = blocked, enabled = allowed. Extensible list — add commands as needed.
   - **Blocked List**: Section showing permanently denied permissions. Plus button opens form: dropdown to select tool from installed tools, text field for the exact command to block. Clicking an existing blocked entry opens popup: "Reset this permission? This renews the model's ability to request this permission (does not grant it)." Yes = remove from blocked list.
   - **Working Directory**: Text field to view/change working directory. If none selected, app creates `workspaces/{sessionTitle}_session` folder and uses it as working directory until changed. Changing here or via chat input plus button updates all app states/screens identically.
   - **Permission Request Popup**: When a tool call triggers a permission check (not perpetually granted or denied), a popup appears inside the Chat tab with options: "This time", "Always", "No", "Never". "Always" = perpetually granted (writes to config.toml). "Never" = added to blocked list in config.toml. "No" = deny this time only. "This time" = approve this instance only. **All permission settings persist to config.toml** — anything configurable in the Settings tab FE persists in the BE config.

### Mobile-First Principles
- **Bottom tab bar**: Anchored to bottom of screen at all times, no dead space underneath, no content cut off by tab bar. Content above tab bar is scrollable (thumb swipe), tab bar stays fixed.
- **Layout**: Strictly single-column, full width of screen. No multi-column/responsive adjustments for tablets or desktop (Phase 2).
- **Priority**: Mobile portrait phone experience is primary, desktop UI is incidental.

## Phase 2 Deferred Features
- Session title inline editing (Chat tab)
- Collapsible/expandable tool call components in chat
- Multi-column/responsive layouts for tablets, landscape, desktop
- Additional tools: web (search/fetch), browser (Playwright), computer (screenshots/input), coding (file edit/git)
- Personas system
- Skills system
- Subagents
- MCP server integration
- Search/filter in History tab
- Advanced permission controls (pattern matching, allow/deny/ask modes beyond boolean toggles)
- Working directory change in Settings
- Desktop-optimized UI tweaks

## Development Approach (Strict BDD/TDD)
1. **Baseline**: Start with `faa9c79` (working-branch tip) as the code baseline
2. **Strip fake tests**: Delete ALL tests that use mocks/fakes instead of testing real user-facing behavior E2E. No exceptions — if it doesn't prove something works for the user, it's useless.
3. **Strip out-of-scope code**: Remove personas, skills, subagents, MCP, web/browser/computer/coding tools from both codebase and tests. Keep only: shell tool, chat streaming, permissions, scheduler, session history, provider discovery.
4. **Clean baseline**: Minimal code + only real behavior tests that actually prove the app works E2E.
5. **Write missing E2E tests**: Cover real WebSocket chat flow, real shell commands through full agent→tool→permission stack, real session persistence to SQLite, real provider ping, real config persistence.
6. **Debug/fix baseline**: Run tests, fix until all pass. No new features until baseline is solid.
7. **100% BDD/TDD for MVP features**: For each tiny piece of work:
   - Write the E2E test for the ideal workflow first
   - Write/fix code to make the test pass
   - Only when all tests pass, move to next piece
   - One feature + test suite at a time
8. **Commit discipline**: All changes committed atomically with clear messages. Nothing added beyond MVP scope.

## Change Log (Tracking strip-down and rebuild steps)
- [2026-05-02] Decided to use `faa9c79` as baseline
- [2026-05-02] Assessed tests at faa9c79: 37 passed, but most are fakes/mocks (test_agent.py uses _FakeCompletions, test_main_api.py uses ASGITransport). Only test_permissions.py, test_shell.py, test_config.py test real behavior.
- [2026-05-02] Created `cleanup-baseline` branch from `faa9c79`
- [2026-05-02] Removed fake test files: test_agent.py, test_main_api.py
- [2026-05-02] Removed out-of-scope test files: test_coding.py, test_web.py, test_personas.py, test_skills.py
- [2026-05-02] Removed out-of-scope code: backend/personas/, backend/skills/, backend/mcp/, backend/subagent.py, backend/agents/
- [2026-05-02] Removed out-of-scope tools: browser.py, coding.py, computer.py, web.py
- [2026-05-02] Rewrote backend/tools/registry.py to only register shell tool
- [2026-05-02] Rewrote backend/config/config.toml for MVP (shell-only, boolean toggles)
- [2026-05-02] Removed out-of-scope frontend components: ComputerView.tsx, PersonaPicker.tsx, AgentsPanel.tsx, Scheduler.tsx, SessionTitle.tsx
- [2026-05-02] Rewrote frontend/src/App.tsx: 3-tab mobile layout (chat, history, settings), bottom tab bar
- [2026-05-02] Rewrote frontend/src/components/Chat.tsx: textarea input, send/stop button, debug bar, permission options updated to "this time"/"always"/"no"/"never"
- [2026-05-02] Rewrote frontend/src/components/Permissions.tsx: MVP design with Tools toggle and Permissions toggle (shell-only)
- [2026-05-02] Rewrote frontend/src/lib/api.ts: removed out-of-scope API functions (schedules)
- [2026-05-02] Updated frontend/src/lib/ws.ts: added `stop` message type
- [2026-05-02] Updated backend/main.py: added stop message handler, HubState now tracks current task + shell PIDs for kill-switch
- [2026-05-02] Backend tests: 20/20 pass after cleanup

## Agreed Decisions Log
- [2026-05-02] MVP scope: chat + streaming + shell tool only, 3-tab mobile UI
- [2026-05-02] Cut personas, skills, subagents, MCP for Phase 1
- [2026-05-02] Session history required for MVP
- [2026-05-02] Mobile is primary purpose, desktop UI incidental
- [2026-05-02] Tailscale-only auth, no additional sign-on
- [2026-05-02] UI/mobile UI resolved first, then extend tool logic
- [2026-05-02] Bottom tab bar: anchored, no dead space, fixed position, scrollable content above
- [2026-05-02] Skip session title edit for MVP (Phase 2)
- [2026-05-02] Settings tab has 3 subsections: Model Providers (text fields), Tools (bash only, toggle), Permissions (per-command boolean toggles)
- [2026-05-02] Tool call output inline full display (no collapse) for MVP
- [2026-05-02] Strictly single-column full width layout for MVP (Phase 2 for wider screens)
