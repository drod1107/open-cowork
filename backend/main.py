"""FastAPI app + WebSocket hub.

Responsibilities:
- Serve the compiled React frontend (if built) as static files.
- Expose REST endpoints for models, schedules, config, permissions, health.
- Run a single WebSocket endpoint that multiplexes:
    * inbound user messages  -> agent.run_stream
    * outbound agent events   -> client
    * inbound permission replies -> permission gate
    * outbound permission requests -> client
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .agent import Agent
from .config_loader import load_config, save_config
from .permissions import PermissionGate, PermissionRequest
from .providers import ProviderClient
from .scheduler import Scheduler
from .tools.registry import build_registry


FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


class HubState:
    """Shared app-wide state kept on `app.state.hub`."""

    def __init__(self) -> None:
        self.gate = PermissionGate()
        self.provider = ProviderClient()
        self.scheduler: Scheduler | None = None
        self._pending_permissions: dict[str, asyncio.Future] = {}
        self._ws_clients: set[WebSocket] = set()
        self._selected_model: str | None = None

    # ------------------------------------------------------------ WS broker
    async def register_ws(self, ws: WebSocket) -> None:
        await ws.accept()
        self._ws_clients.add(ws)

    def unregister_ws(self, ws: WebSocket) -> None:
        self._ws_clients.discard(ws)

    async def broadcast(self, event: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self._ws_clients:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for d in dead:
            self._ws_clients.discard(d)

    # ------------------------------------------------ permission prompter
    async def prompt_permission(self, request: PermissionRequest) -> dict[str, Any]:
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_permissions[request.request_id] = future
        await self.broadcast(
            {
                "type": "permission_request",
                "request": {
                    "id": request.request_id,
                    "category": request.category,
                    "action": request.action,
                    "description": request.description,
                },
            }
        )
        try:
            return await future
        finally:
            self._pending_permissions.pop(request.request_id, None)

    def resolve_permission(self, request_id: str, decision: str) -> bool:
        future = self._pending_permissions.get(request_id)
        if future is None or future.done():
            return False
        future.set_result({"decision": decision})
        return True

    # ------------------------------------------------------ model selection
    def select_model(self, model: str) -> None:
        self._selected_model = model

    @property
    def selected_model(self) -> str | None:
        return self._selected_model

    # ---------------------------------------------------------- build agent
    def build_agent(self, working_dir: str) -> Agent:
        cfg = load_config()
        model = self._selected_model or cfg.get("default_model") or ""
        if not model:
            raise RuntimeError("No model selected. Pick one in the UI or set default_model in config.")
        base_url = cfg.get("base_url", "http://localhost:11434")
        # Ollama uses the /v1 suffix for OpenAI compat.
        if cfg.get("provider") == "ollama" and not base_url.rstrip("/").endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"
        system_prompt = cfg.get("agent", {}).get("system_prompt", "")
        max_turns = int(cfg.get("agent", {}).get("max_turns", 50))
        agent = Agent(
            model=model,
            base_url=base_url,
            system_prompt=system_prompt,
            max_turns=max_turns,
        )
        agent.tools = build_registry(self.gate, working_dir=working_dir)
        return agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    hub = HubState()
    app.state.hub = hub
    hub.gate.set_prompter(hub.prompt_permission)

    # Task runner for scheduled jobs: run a fresh agent and broadcast events.
    async def _task_runner(description: str) -> None:
        cfg = load_config()
        working_dir = cfg.get("runtime", {}).get("working_dir", ".")
        try:
            agent = hub.build_agent(working_dir)
        except Exception as exc:
            await hub.broadcast({"type": "scheduler_error", "error": str(exc)})
            return
        await hub.broadcast(
            {"type": "scheduler_start", "description": description}
        )
        async for event in agent.run_stream(description):
            await hub.broadcast({"type": "scheduler_event", "event": event})
        await hub.broadcast({"type": "scheduler_end", "description": description})

    hub.scheduler = Scheduler(task_runner=_task_runner)
    hub.scheduler.start()

    try:
        yield
    finally:
        if hub.scheduler:
            hub.scheduler.shutdown()
        await hub.provider.close()


app = FastAPI(title="OpenCowork", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_hub(request_or_ws) -> HubState:
    return request_or_ws.app.state.hub


# ------------------------------------------------------------------- health
@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ------------------------------------------------------------------- models
@app.get("/api/models")
async def list_models(force: bool = False) -> dict[str, Any]:
    hub: HubState = app.state.hub
    try:
        models = await hub.provider.list_models(force=force)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"provider error: {exc}")
    return {
        "provider": hub.provider.provider,
        "base_url": hub.provider.base_url,
        "models": [m.to_dict() for m in models],
        "selected": hub.selected_model,
    }


@app.post("/api/models/select")
async def select_model(payload: dict[str, Any]) -> dict[str, Any]:
    hub: HubState = app.state.hub
    model = payload.get("model")
    if not model:
        raise HTTPException(400, "missing `model`")
    hub.select_model(model)
    return {"selected": model}


# ----------------------------------------------------------------- schedules
@app.get("/api/schedules")
async def list_schedules() -> dict[str, Any]:
    hub: HubState = app.state.hub
    assert hub.scheduler
    return {"schedules": [j.to_dict() for j in hub.scheduler.list()]}


@app.post("/api/schedules")
async def create_schedule(payload: dict[str, Any]) -> dict[str, Any]:
    hub: HubState = app.state.hub
    assert hub.scheduler
    description = payload.get("description")
    cron = payload.get("cron")
    if not description or not cron:
        raise HTTPException(400, "description and cron are required")
    job = hub.scheduler.add(description, cron, job_id=payload.get("id"))
    return job.to_dict()


@app.delete("/api/schedules/{job_id}")
async def delete_schedule(job_id: str) -> dict[str, Any]:
    hub: HubState = app.state.hub
    assert hub.scheduler
    ok = hub.scheduler.remove(job_id)
    return {"removed": ok}


# ------------------------------------------------------------------- config
@app.get("/api/config")
async def read_config() -> dict[str, Any]:
    return load_config()


@app.put("/api/config")
async def write_config(payload: dict[str, Any]) -> dict[str, Any]:
    save_config(payload)
    return {"ok": True}


# -------------------------------------------------------------- WebSocket
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    hub: HubState = websocket.app.state.hub
    await hub.register_ws(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "error": "bad json"})
                continue
            mtype = message.get("type")

            if mtype == "chat":
                user_text = message.get("text", "")
                cfg = load_config()
                working_dir = cfg.get("runtime", {}).get("working_dir", ".")
                try:
                    agent = hub.build_agent(working_dir)
                except Exception as exc:
                    await websocket.send_json({"type": "error", "error": str(exc)})
                    continue
                async for event in agent.run_stream(user_text):
                    await websocket.send_json(event)

            elif mtype == "permission_response":
                rid = message.get("id") or ""
                decision = message.get("decision") or "deny"
                ok = hub.resolve_permission(rid, decision)
                await websocket.send_json(
                    {"type": "permission_resolved", "id": rid, "ok": ok}
                )

            elif mtype == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                await websocket.send_json(
                    {"type": "error", "error": f"unknown message type: {mtype}"}
                )
    except WebSocketDisconnect:
        hub.unregister_ws(websocket)
    except Exception as exc:  # pragma: no cover - defensive
        await websocket.send_json({"type": "error", "error": str(exc)})
        hub.unregister_ws(websocket)


# --------------------------------------------------------------- static
if FRONTEND_DIST.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIST), html=True),
        name="frontend",
    )
else:
    @app.get("/")
    async def _root() -> JSONResponse:
        return JSONResponse(
            {
                "message": "OpenCowork backend is running. Build the frontend (cd frontend && npm run build) to serve the UI here.",
                "docs": "/docs",
            }
        )


def run() -> None:  # pragma: no cover - entrypoint
    import uvicorn

    host = os.environ.get("OPENCOWORK_HOST", "0.0.0.0")
    port = int(os.environ.get("OPENCOWORK_PORT", "7337"))
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":  # pragma: no cover
    run()
