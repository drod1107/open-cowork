"""Tests for Session REST endpoints.

From PR-reviews.md TDD Process Audit (2026-05-03):
- Session REST endpoints: /api/sessions GET/PATCH/DELETE in main.py
- Needs test coverage per TDD process

From Dev-Plan.md Phase 1 (lines 119-121):
- GET /api/sessions - list all sessions
- GET /api/sessions/{id} - get session with messages
- PATCH /api/sessions/{id} - update metadata (title)
- DELETE /api/sessions/{id} - delete session
"""

import pytest
from fastapi.testclient import TestClient


def test_get_sessions_returns_list(tmp_config, monkeypatch):
    """Verify GET /api/sessions returns a list of sessions.

    From Dev-Plan.md:119 - list all sessions.
    """
    from backend.main import app
    from backend import sessions as sessions_mod
    import sqlite3
    
    # Setup test DB
    db_path = tmp_config.parent / "sessions.db"
    monkeypatch.setattr(sessions_mod, "DB_PATH", db_path)
    sessions_mod.init_db()
    
    client = TestClient(app)
    response = client.get("/api/sessions")
    
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_session_by_id(tmp_config, monkeypatch):
    """Verify GET /api/sessions/{id} returns session with messages.

    From Dev-Plan.md:120 - get session with messages.
    """
    from backend.main import app
    from backend import sessions as sessions_mod
    import sqlite3
    
    # Setup test DB
    db_path = tmp_config.parent / "sessions.db"
    monkeypatch.setattr(sessions_mod, "DB_PATH", db_path)
    sessions_mod.init_db()
    
    # Create a test session
    session_id = sessions_mod.create_session()
    sessions_mod.append_message(session_id, "user", "Hello")
    sessions_mod.append_message(session_id, "assistant", "Hi there!")
    
    client = TestClient(app)
    response = client.get(f"/api/sessions/{session_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "messages" in data
    assert len(data["messages"]) > 0


def test_patch_session_updates_metadata(tmp_config, monkeypatch):
    """Verify PATCH /api/sessions/{id} updates metadata.

    From Dev-Plan.md:121 - update metadata (title).
    """
    from backend.main import app
    from backend import sessions as sessions_mod
    
    # Setup test DB
    db_path = tmp_config.parent / "sessions.db"
    monkeypatch.setattr(sessions_mod, "DB_PATH", db_path)
    sessions_mod.init_db()
    
    # Create a test session
    session_id = sessions_mod.create_session()
    
    client = TestClient(app)
    response = client.patch(
        f"/api/sessions/{session_id}",
        json={"title": "New Title"}
    )
    
    assert response.status_code == 200
    
    # Verify update
    get_response = client.get(f"/api/sessions/{session_id}")
    data = get_response.json()
    assert data.get("metadata", {}).get("title") == "New Title"


def test_delete_session_returns_deleted_true(tmp_config, monkeypatch):
    """Verify DELETE /api/sessions/{id} returns {deleted: true}.

    From Dev-Plan.md:122 - delete session.
    """
    from backend.main import app
    from backend import sessions as sessions_mod
    
    # Setup test DB
    db_path = tmp_config.parent / "sessions.db"
    monkeypatch.setattr(sessions_mod, "DB_PATH", db_path)
    sessions_mod.init_db()
    
    # Create a test session
    session_id = sessions_mod.create_session()
    
    client = TestClient(app)
    response = client.delete(f"/api/sessions/{session_id}")
    
    assert response.status_code == 200
    assert response.json().get("deleted") is True
    
    # Verify deleted
    get_response = client.get(f"/api/sessions/{session_id}")
    assert get_response.status_code == 404
