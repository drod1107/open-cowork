# Phase 1 Implementation Plan - Streamlined Mobile-First POC

## Goal
Build a streamlined, mobile-first OpenCowork POC based on README.md specification:
- **Mobile-first design** - works on mobile, usable on desktop
- **Simplified feature set** - Core functionality only
- **BDD approach** - Test first, implement, verify, commit

## Phase 1 Features (from README)

### Backend (Python FastAPI)
- [x] FastAPI app with WebSocket hub
- [x] Agent loop (OpenAI-compatible API)
- [x] Permission gate (ask/allow/deny)
- [x] Provider auto-discovery (Ollama, LM Studio, vLLM, SGLang)
- [x] Config loader (TOML)
- [x] Tools: shell, web (fetch + search), browser (Playwright MCP), computer, coding
- [x] REST endpoints for models, sessions, config
- [x] WebSocket protocol for chat streaming

### Frontend (React + TypeScript + Vite + Tailwind)
- [ ] **Mobile-first layout** - single column on mobile, optional side panel on desktop
- [ ] **Chat interface** - streaming messages, tool call display
- [ ] **ModelPicker** - select model from active provider
- [ ] **ProviderPicker** - switch between providers
- [ ] **Permissions panel** - view/modify allow/block rules
- [ ] **ComputerView** - display desktop screenshots
- [ ] **Sidebar** - session list (simplified, no personas/skills)

### Networking
- [x] Serve on 0.0.0.0:7337
- [x] Tailscale-compatible (no auth beyond tailnet)
- [ ] WebSocket + REST APIs working on mobile devices

## Simplifications for Phase 1
- **Remove**: Personas system (backend/personas/)
- **Remove**: Skills system (backend/skills/)
- **Remove**: Subagents (backend/subagent.py, frontend/components/AgentsPanel.tsx)
- **Remove**: MCP servers (backend/mcp/, backend/config/mcp_servers.toml)
- **Remove**: Scheduler / cron-for-AI (moved to Phase 2 — APScheduler spec in Dev-Plan.md)
- **Remove**: ComputerView (out of scope for MVP)
- **Simplify**: Chat to core functionality only (no slash commands for personas/skills/agents)
- **Simplify**: Sidebar - session list only, no complex features
- **Keep**: Stop button, mobile debug bar (useful for testing)

## BDD Execution Strategy
1. Write test for feature
2. Run test (should fail)
3. Implement minimal code to pass test
4. Run test (should pass)
5. Manual verification on mobile device via Tailscale
6. Commit atomically with clear message
7. Restart dev server
8. Report status
9. Move to next feature

## Test Order
1. Backend tests all pass (baseline: 81 passing)
2. Frontend: Fix 6 failing tests (baseline: 36 passing)
3. Simplify backend (remove personas/skills/subagents/mcp)
4. Simplify frontend (remove complex features)
5. Mobile-first layout implementation
6. Integration testing on mobile device

## Verification Checklist (features user can manually verify)
- [ ] Server starts on :7337
- [ ] Mobile: Chat works (type message, get streaming response)
- [ ] Mobile: Model picker works
- [ ] Mobile: Provider switching works
- [ ] Mobile: Tool calls visible in chat
- [ ] Mobile: Permissions panel works
- [ ] Desktop: Usable layout (not optimized, but works)
- [ ] All features work over Tailscale on mobile device
