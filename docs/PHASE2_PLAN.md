# Phase 2 Plan — OpenCowork

## Scope

Phase 2 adds 8 features. Each gets its own `feature/{name}` branch cut from `dev`, with atomic commits and its own PR into `dev`. A phase is "done" when all its feature PRs are merged.

### Feature List

| # | Feature | Branch | Description |
|---|---------|--------|-------------|
| 1 | Skills System | `feature/skills` | Markdown skill files, context injection via `/use-skill` |
| 2 | MCP Server Integration | `feature/mcp` | Model Context Protocol support |
| 3 | Web Tool | `feature/web-tool` | fetch + search |
| 4 | Session Title Inline Editing | `feature/session-title` | Click-to-edit in Chat tab |
| 5 | Working Directory Setting UI | `feature/working-dir-ui` | Text field in Settings tab |
| 6 | Kill-Switch for Non-Shell Tools | `feature/kill-switch-extend` | Browser session terminate, etc. |
| 7 | E2E Test Suite | `feature/e2e-tests` | Playwright tests (stale ones exist, need rewrite) |
| 8 | Custom Provider Form | `feature/custom-provider` | Plus button in Settings to add custom provider |

---

## Feature Specs

### 1. Skills System

**Concept:** Markdown skill files that the agent can load to gain specialized context. A skill is a `.md` file containing instructions, examples, and domain knowledge that gets injected into the agent's context when the user invokes `/use-skill {name}`.

**Backend:**
- `backend/skills/` directory for skill `.md` files
- Skill discovery: scan directory, index by filename (minus extension)
- `/use-skill` command parser in chat handler
- Skill injection: prepend skill content to system prompt or as a system-adjacent message
- Config entry: `skills_dir` in config.toml (default `backend/skills/`)

**Frontend:**
- Skills list in Settings tab (new subsection or under Tools)
- Toggle to enable/disable individual skills
- `/use-skill {name}` autocomplete in chat input

**User Stories:**
1. User types `/use-skill code-review` → agent gains code review expertise for that session
2. User browses available skills in Settings
3. User creates custom skill by dropping a `.md` file in the skills directory
4. User disables a skill they don't want the agent to auto-load

---

### 2. MCP Server Integration

**Concept:** Support Model Context Protocol servers that provide additional tools and context to the agent. MCP servers run as separate processes and communicate via stdio/SSE.

**Backend:**
- `backend/mcp/` module for MCP client implementation
- `backend/config/mcp_servers.toml` for MCP server configuration
- MCP client connects to configured servers, discovers their tools
- Tools from MCP servers registered alongside built-in tools
- Tool calls routed to appropriate MCP server via MCP protocol
- `install-mcp.sh` script (already exists, needs update)

**Frontend:**
- MCP servers section in Settings tab
- Add MCP server form (name, command, args)
- Server status indicator (connected/disconnected)
- MCP tools appear in Tools list alongside built-in tools

**User Stories:**
1. User adds a Playwright MCP server → browser tool becomes available
2. User sees MCP server connection status in Settings
3. User adds/removes MCP servers via Settings UI
4. MCP tools respect the same permission gate as built-in tools

---

### 3. Web Tool

**Concept:** Allow the agent to fetch URLs and search the web. Two sub-capabilities: URL fetching and web search.

**Backend:**
- `backend/tools/web.py` — two functions: `fetch_url(url)` and `search_web(query)`
- `fetch_url`: HTTP GET, return content (with size limit, content-type filtering)
- `search_web`: configurable search backend (DuckDuckGo, Searx, etc.)
- Permission category: `web` with per-action defaults (already scaffolded in `permissions.py:93-95`)
- Kill-switch extension: interrupt in-flight HTTP requests

**Frontend:**
- Web tool toggle in Settings → Tools subsection
- Permission entries for `search_web` and `fetch_url`

**User Stories:**
1. Agent fetches a URL and reads its content
2. Agent searches the web for information
3. User can toggle web tool on/off
4. User can permission-gate search vs fetch independently

---

### 4. Session Title Inline Editing

**Concept:** The session ID in the Chat tab top bar becomes a click-to-edit field. User clicks → text input → types new title → presses Enter or clicks away → title saved to session metadata.

**Backend:**
- `PATCH /api/sessions/{id}` endpoint to update session metadata (title field)
- Sessions table already has `metadata` JSON column — store `title` there

**Frontend:**
- Session ID display becomes an editable text field
- Click to edit, Enter to save, Escape to cancel
- New sessions get auto-generated title (e.g., first 50 chars of first message)
- Title displayed in History tab session list

**User Stories:**
1. User clicks session title in Chat tab → edits it → new title persists
2. User sees custom titles in History tab
3. New sessions get a sensible default title

---

### 5. Working Directory Setting UI

**Concept:** Settings tab gets a text field showing the current working directory, editable by the user. Changing it updates the backend's `working_dir` config and all app state.

**Backend:**
- `config.toml` already has `[runtime] working_dir = "."` (read by `main.py:335`)
- `PATCH /api/config` endpoint to update working_dir
- Changing working_dir updates the shell tool's CWD

**Frontend:**
- Text field in Settings tab showing current working directory
- Editable with folder picker option
- If none selected, display default behavior
- Changes propagate to chat input plus button state

**User Stories:**
1. User sees current working directory in Settings
2. User changes working directory → all subsequent shell commands run in new directory
3. User selects folder via chat input plus button → Settings updates too

---

### 6. Kill-Switch for Non-Shell Tools

**Concept:** Extend the kill-switch pattern to work with tool types beyond shell. Each tool type stores its own process/session identifiers in HubState, and `stop_current()` kills them appropriately.

**Backend:**
- `HubState` gets extensible tool PID/session tracking (not just `_current_shell_pids`)
- Each tool type defines its own kill method:
  - Shell: SIGTERM-first, then SIGKILL (already implemented)
  - Web: cancel in-flight HTTP requests
  - Browser: terminate Playwright session
  - MCP: send shutdown signal to MCP server process
- `stop_current()` iterates through all active tool identifiers and dispatches to the appropriate kill method

**Frontend:**
- No UI changes needed — stop button already exists and works generically

**User Stories:**
1. User clicks Stop while agent is browsing → browser session terminates
2. User clicks Stop while agent is fetching a URL → HTTP request cancelled
3. Kill-switch works consistently regardless of which tool is active

---

### 7. E2E Test Suite (Playwright)

**Concept:** Rewrite the stale E2E test files to match the current MVP UI. Existing files reference non-existent test IDs and removed components.

**Current state:**
- `tools-panel.spec.ts` — references tool rows, MCP install form, custom tool forms that don't exist
- `opencowork.spec.ts` — references permission panel and default-shell selector that don't match current UI
- `mobile-history.spec.ts` — references `tab-chats` (should be `tab-history`), stale test IDs

**Task:**
- Rewrite all 3 spec files to test actual current UI
- Add new specs for: settings tab, chat flow, permission popup, provider switching
- Run in CI (or locally via `npm run e2e`)
- Test IDs must be added to components where missing

**User Stories:**
1. `npm run e2e` runs and passes against the current deployed app
2. E2E tests cover: chat flow, history tab, settings tab, permission popup, provider switching
3. E2E tests serve as regression guard for future phases

---

### 8. Custom Provider Form

**Concept:** Settings tab gets a "Model Providers" subsection with a list of configured providers and a plus button. Clicking the plus button opens a popup form to add a new provider. The form has a dropdown of common local providers (Ollama, LM Studio, vLLM, SGLang, NVIDIA) plus a "Custom" option. Selecting a known provider pre-populates its default base_url (and any provider-specific fields); selecting "Custom" opens a blank form. User saves → provider is added to config and appears in the list.

**Backend:**
- Already supports `openai-compat` provider type in `providers.py`
- Config already supports multiple providers in `config.toml` (under `[providers]` section)
- `POST /api/providers` endpoint to add a new provider to config
- `DELETE /api/providers/{name}` endpoint to remove a custom provider (built-ins rejected with 403)

**Frontend:**
- Settings tab gets a "Model Providers" subsection above Tools
- Provider list showing all configured providers (name + type)
- Plus button at top-right of the subsection
- Clicking plus → popup form with:
  - Provider type dropdown: Ollama, LM Studio, vLLM, SGLang, NVIDIA, Custom
  - Known providers pre-populate base_url with their defaults:
    - Ollama → `http://localhost:11434`
    - LM Studio → `http://localhost:1234`
    - vLLM → `http://localhost:8000`
    - SGLang → `http://localhost:30000`
    - NVIDIA → `https://integrate.api.nvidia.com`
  - Custom → all fields blank, no pre-population
  - Fields: Nickname (required), Base URL (required), API Key (optional, for NVIDIA/Custom)
  - Save writes to config.toml, provider appears in list
  - Provider list items have a delete button (greyed out / disabled for built-in providers)
- Default Ollama provider is pre-selected by default
- This is the ONLY way to add providers — no text box clutter in the main UI

**User Stories:**
1. User goes to Settings > Model Providers, sees Ollama pre-selected as default
2. User clicks plus button → selects "LM Studio" from dropdown → base_url pre-populated with `http://localhost:1234` → saves → LM Studio appears in provider list
3. User clicks plus button → selects "Custom" → fills in nickname, base_url, API key → saves → custom provider appears in list
4. User deletes a custom provider from the list → it's removed from config
5. User cannot delete built-in providers (Ollama) — delete button disabled

---

## Implementation Order (Suggested)

1. **Custom Provider Form** — smallest scope, unblocks real provider testing
2. **Working Directory Setting UI** — small scope, config already exists
3. **Session Title Inline Editing** — small scope, improves daily UX
4. **Kill-Switch for Non-Shell Tools** — prerequisite for web tool
5. **Web Tool** — depends on kill-switch extension
6. **Skills System** — new feature system, moderate scope
7. **MCP Server Integration** — largest scope, depends on tool infrastructure
8. **E2E Test Suite** — can be done in parallel, validates everything

## Git Workflow

All Phase 2 features follow this pattern:
1. Cut `feature/{name}` from `dev`
2. Implement with atomic commits (TDD: tests first where applicable)
3. Open PR from `feature/{name}` → `dev`
4. QA reviews via PR-reviews.md
5. PM approves
6. Merge PR
7. Phase 2 complete when all 8 PRs merged
