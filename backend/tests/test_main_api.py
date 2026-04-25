"""Exercises the FastAPI REST surface with httpx.AsyncClient + ASGITransport,
avoiding the need to spin up a real server."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

import backend.config_loader as config_loader


pytestmark = pytest.mark.asyncio


@pytest.fixture()
async def client(tmp_config, monkeypatch):
    # Redirect default config path at load time.
    monkeypatch.setattr(config_loader, "DEFAULT_CONFIG_PATH", tmp_config)
    # Ensure APScheduler writes its jobs db into a tmp path.
    import backend.scheduler as scheduler_mod

    monkeypatch.setattr(scheduler_mod, "DB_PATH", Path(tmp_config).parent / "jobs.db")

    # Re-import app to honor patched paths (the lifespan reads DEFAULT_CONFIG_PATH lazily anyway).
    from backend.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as _:
            pass
        # trigger lifespan
        async with app.router.lifespan_context(app):  # type: ignore[attr-defined]
            yield c


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_models_endpoint_with_mock(client, monkeypatch):
    async def fake_list(self, force: bool = False):
        from backend.providers import Model

        return [Model(id="fake-model", supports_vision=None)]

    from backend.providers import ProviderClient

    monkeypatch.setattr(ProviderClient, "list_models", fake_list)
    r = await client.get("/api/models")
    assert r.status_code == 200
    data = r.json()
    assert data["models"][0]["id"] == "fake-model"


async def test_select_model_stores_selection(client):
    r = await client.post("/api/models/select", json={"model": "hello"})
    assert r.status_code == 200
    assert r.json()["selected"] == "hello"


async def test_config_roundtrip(client):
    r = await client.get("/api/config")
    assert r.status_code == 200
    cfg = r.json()
    cfg["provider"] = "vllm"
    r2 = await client.put("/api/config", json=cfg)
    assert r2.status_code == 200
    r3 = await client.get("/api/config")
    assert r3.json()["provider"] == "vllm"


async def test_schedules_crud(client):
    r = await client.post(
        "/api/schedules",
        json={"description": "wake up", "cron": "0 9 * * *", "id": "abc"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "abc"
    # Regression: cron must come back exactly as submitted, not field-reordered.
    assert body["cron"] == "0 9 * * *"

    r2 = await client.get("/api/schedules")
    listed = r2.json()["schedules"]
    found = next(s for s in listed if s["id"] == "abc")
    assert found["cron"] == "0 9 * * *"

    r3 = await client.delete("/api/schedules/abc")
    assert r3.status_code == 200
    assert r3.json()["removed"] is True


async def test_websocket_chat_without_model_emits_error(client, monkeypatch):
    """Regression: sending chat without a selected model used to return nothing
    visible; the FE was left 'thinking' forever. Verify an error event arrives."""
    from backend.main import app
    from starlette.testclient import TestClient

    with TestClient(app) as tc:
        with tc.websocket_connect("/ws") as ws:
            ws.send_json({"type": "chat", "text": "hi"})
            event = ws.receive_json(mode="text")
            assert event["type"] == "error"
            assert "model" in event["error"].lower()


async def test_websocket_ping_pongs(client):
    from backend.main import app
    from starlette.testclient import TestClient

    with TestClient(app) as tc:
        with tc.websocket_connect("/ws") as ws:
            ws.send_json({"type": "ping"})
            event = ws.receive_json(mode="text")
            assert event == {"type": "pong"}


async def test_websocket_unknown_message_type_returns_error(client):
    from backend.main import app
    from starlette.testclient import TestClient

    with TestClient(app) as tc:
        with tc.websocket_connect("/ws") as ws:
            ws.send_json({"type": "nope"})
            event = ws.receive_json(mode="text")
            assert event["type"] == "error"
            assert "unknown" in event["error"].lower()
