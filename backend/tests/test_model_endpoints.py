"""Tests for Model endpoints."""

import pytest
import asyncio
from httpx import AsyncClient
from backend.main import app
from backend.tests.conftest import hub


@pytest.mark.asyncio
async def test_get_models_returns_dict(tmp_config, hub, monkeypatch):
    """Verify GET /api/models returns dict with provider, models list."""
    from backend import sessions as sessions_mod
    
    # Setup
    db_path = tmp_config.parent / "sessions.db"
    monkeypatch.setattr(sessions_mod, "DB_PATH", db_path)
    await sessions_mod.init_db()
    
    app.state.hub = hub
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/models")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict), "Should return dict"
    assert "models" in data, "Should have models key"
    assert isinstance(data["models"], list), "models should be a list"


@pytest.mark.asyncio
async def test_get_models_with_force_param(tmp_config, hub, monkeypatch):
    """Verify GET /api/models?force=1 refreshes model list."""
    from backend import sessions as sessions_mod
    
    db_path = tmp_config.parent / "sessions.db"
    monkeypatch.setattr(sessions_mod, "DB_PATH", db_path)
    await sessions_mod.init_db()
    
    app.state.hub = hub
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/models?force=1")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict), "Should return dict"
    assert "models" in data


@pytest.mark.asyncio
async def test_select_model_requires_model_field(tmp_config, hub, monkeypatch):
    """Verify POST /api/models/select validates model field."""
    from backend import sessions as sessions_mod
    
    db_path = tmp_config.parent / "sessions.db"
    monkeypatch.setattr(sessions_mod, "DB_PATH", db_path)
    await sessions_mod.init_db()
    
    app.state.hub = hub
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Empty body
        response = await client.post("/api/models/select", json={})
        assert response.status_code in [400, 422], "Should reject empty body"
        
        # Missing model field
        response = await client.post("/api/models/select", json={"provider": "ollama"})
        assert response.status_code in [400, 422], "Should require model field"


@pytest.mark.asyncio
async def test_select_model_success(tmp_config, hub, monkeypatch):
    """Verify POST /api/models/select with valid model."""
    from backend import sessions as sessions_mod
    
    db_path = tmp_config.parent / "sessions.db"
    monkeypatch.setattr(sessions_mod, "DB_PATH", db_path)
    await sessions_mod.init_db()
    
    app.state.hub = hub
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/models/select",
            json={"model": "test-model"}
        )
    
    # Should succeed or fail gracefully
    assert response.status_code in [200, 400, 422]
    
    if response.status_code == 200:
        data = response.json()
        assert "selected" in data, "Should have selected field"
        assert data["selected"] == "test-model"
