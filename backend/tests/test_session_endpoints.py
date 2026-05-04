"""Tests for Session REST endpoints.

From PR-reviews.md TDD Process Audit (2026-05-03):
- Session REST endpoints: /api/sessions GET/PATCH/DELETE in main.py
- Needs test coverage per TDD process

From Dev-Plan.md Phase 1 (lines 119-122):
- GET /api/sessions - list all sessions
- GET /api/sessions/{id} - get session with messages
- PATCH /api/sessions/{id} - update metadata (title)
- DELETE /api/sessions/{id} - delete session
"""

import pytest
import asyncio
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_sessions_returns_list(tmp_config, monkeypatch):
    """Verify GET /api/sessions returns a list of sessions.

    From Dev-Plan.md:119 - list all sessions.
    Dev's shape: {"sessions": [...]}
    """
    from backend.main import app
    from backend import sessions as sessions_mod
    
    # Setup test DB
    db_path = tmp_config.parent / "sessions.db"
    monkeypatch.setattr(sessions_mod, "DB_PATH", db_path)
    await sessions_mod.init_db()
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/sessions")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict), "Should return dict"
    assert "sessions" in data, "Should have sessions key"
    assert isinstance(data["sessions"], list), "sessions should be a list"


@pytest.mark.asyncio
async def test_get_session_by_id(tmp_config, monkeypatch):
    """Verify GET /api/sessions/{id} returns session with messages.

    From Dev-Plan.md:120 - get session with messages.
    """
    from backend.main import app
    from backend import sessions as sessions_mod
    
    # Setup test DB
    db_path = tmp_config.parent / "sessions.db"
    monkeypatch.setattr(sessions_mod, "DB_PATH", db_path)
    await sessions_mod.init_db()
    
    # Create a test session (await async function)
    session_dict = await sessions_mod.create_session()
    session_id = session_dict["id"]  # Extract the ID string from dict
    await sessions_mod.append_message(session_id, "user", "Hello")
    await sessions_mod.append_message(session_id, "assistant", "Hi there!")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(f"/api/sessions/{session_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "messages" in data
    assert len(data["messages"]) > 0


@pytest.mark.asyncio
async def test_patch_session_updates_metadata(tmp_config, monkeypatch):
    """Verify PATCH /api/sessions/{id} updates metadata.

    From Dev-Plan.md:121 - update metadata (title).
    Dev's return: {"ok": True}
    """
    from backend.main import app
    from backend import sessions as sessions_mod
    
    # Setup test DB
    db_path = tmp_config.parent / "sessions.db"
    monkeypatch.setattr(sessions_mod, "DB_PATH", db_path)
    await sessions_mod.init_db()
    
    # Create a test session (await async function)
    session_dict = await sessions_mod.create_session()
    session_id = session_dict["id"]  # Extract the ID string
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.patch(
            f"/api/sessions/{session_id}",
            json={"metadata": {"title": "New Title"}}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data.get("ok") is True, "Should return ok: true"
    
    # Verify update
    async with AsyncClient(app=app, base_url="http://test") as client2:
        get_response = await client2.get(f"/api/sessions/{session_id}")
    data = get_response.json()
    assert data.get("metadata", {}).get("title") == "New Title"


@pytest.mark.asyncio
async def test_delete_session_returns_deleted_true(tmp_config, monkeypatch):
    """Verify DELETE /api/sessions/{id} returns {deleted: true}.

    From Dev-Plan.md:122 - delete session.
    Dev's return: {"deleted": True/False}
    """
    from backend.main import app
    from backend import sessions as sessions_mod
    
    # Setup test DB
    db_path = tmp_config.parent / "sessions.db"
    monkeypatch.setattr(sessions_mod, "DB_PATH", db_path)
    await sessions_mod.init_db()
    
    # Create a test session (await async function)
    session_dict = await sessions_mod.create_session()
    session_id = session_dict["id"]  # Extract the ID string
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.delete(f"/api/sessions/{session_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data.get("deleted") is True, "Should return deleted: true"
    
    # Verify deleted
    async with AsyncClient(app=app, base_url="http://test") as client2:
        get_response = await client2.get(f"/api/sessions/{session_id}")
    assert get_response.status_code == 404
