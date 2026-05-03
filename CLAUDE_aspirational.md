# CLAUDE.md - Context Localization Guide for OpenCowork

## Introduction
This document provides a structured map of the OpenCowork repository to help AI agents efficiently locate context-relevant files and directories for any given query.

## Project Structure
```
opencowork/
├── backend/                     # Core backend implementation
├── frontend/                  # Frontend application
├── mcp/                       # MCP configuration
├── install.sh                 # Installation script
└── README.md                  # Project overview
```

## Backend Architecture
### Core Components
- `main.py`: FastAPI application entry point and WebSocket hub
- `agent.py`: Main agent loop implementing OpenAI-compatible API
- `permissions.py`: Permission gating system with allow/block lists
- `scheduler.py`: APScheduler implementation with SQLite persistence

### Configuration
- `config/config.toml`: Central configuration file containing:
  - Provider selection (ollama, lmstudio, vllm, sglang)
  - Base URL for selected provider
  - Permission rules with pattern matching

### Tools System
`tools/` directory contains:
- `shell.py`: Command execution with safety controls
- `web.py`: Web search and URL fetching
- `browser.py`: Playwright MCP integration
- `computer.py`: Desktop control utilities (xdotool, spectacle, etc)
- `coding.py`: Code editing and git operations
- `registry.py`: Tool specification registry

### Testing
- `tests/` directory contains:
  - Pytest suite for backend (pytest + httpx + respx)
  - Vitest suite for frontend (testing-library)

## Frontend Architecture
- `src/` directory contains:
  - `App.tsx`: Main application component
  - `components/`: UI components (Chat, ModelPicker, Scheduler, Permissions, ComputerView)
  - `lib/`: Utility functions (api.ts, ws.ts)
  - `__tests__/`: Unit and integration tests

## Security Model
- No built-in authentication
- Relies on Tailscale network boundary
- Permission gate in `permissions.py` controls all tool calls
- Hard-blocked shell patterns in config.toml

## Development Workflow
1. Install dependencies with `./install.sh`
2. Run server: `python -m backend.main`
3. Access UI at http://localhost:7337
4. Configure via `backend/config/config.toml`

## Search Strategy for AI Agents
When seeking context for a query, prioritize:
1. Check `config/config.toml` for configuration context
2. Inspect relevant tool implementations in `tools/`
3. Consult permission rules in `permissions.py`
4. Review test cases in `tests/` for implementation examples
5. Check frontend components in `src/components/` for UI context

This document will be updated as the project evolves to maintain accurate context mapping.