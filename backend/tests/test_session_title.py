"""Tests for Session Title Inline Editing feature (Phase 2, Feature #3).

Verifies:
- PATCH /api/sessions/{id} with metadata.title updates session
- Updated title persists across GET
- 404 for nonexistent session
- Empty title allowed (allows clearing)
"""
import pytest
from httpx import AsyncClient
from backend.main import app
from backend import sessions as sessions_mod


@pytest.mark.asyncio
async def test_patch_session_title_updates_metadata(tmp_config, monkeypatch):
    """Test PATCH /api/sessions/{id} with metadata.title updates session metadata."""
    # Setup test DB
    db_path = tmp_config.parent / "sessions.db"
    monkeypatch.setattr(sessions_mod, "DB_PATH", db_path)
    await sessions_mod.init_db()
    
    # Create a test session
    session_dict = await sessions_mod.create_session()
    session_id = session_dict["id"]
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.patch(
            f"/api/sessions/{session_id}",
            json={"metadata": {"title": "My Custom Title"}}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["title"] == "My Custom Title"


@pytest.mark.asyncio
async def test_patch_session_title_persists_across_get(tmp_config, monkeypatch):
    """Test after PATCH, GET /api/sessions/{id} returns updated title."""
    # Setup test DB
    db_path = tmp_config.parent / "sessions.db"
    monkeypatch.setattr(sessions_mod, "DB_PATH", db_path)
    await sessions_mod.init_db()
    
    # Create a test session
    session_dict = await sessions_mod.create_session()
    session_id = session_dict["id"]
    
    # Set title
    async with AsyncClient(app=app, base_url="http://test") as client:
        await client.patch(
            f"/api/sessions/{session_id}",
            json={"metadata": {"title": "Persistent Title"}}
        )
        
        # Get session and verify title persists
        response = await client.get(f"/api/sessions/{session_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["title"] == "Persistent Title"


@pytest.mark.asyncio
async def test_patch_session_title_on_nonexistent_session():
    """Test PATCH with invalid session_id returns 404."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.patch(
            "/api/sessions/nonexistent-session-12345",
            json={"metadata": {"title": "Test"}}
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_session_empty_title(tmp_config, monkeypatch):
    """Test PATCH with empty title saves empty string (allows clearing title)."""
    # Setup test DB
    db_path = tmp_config.parent / "sessions.db"
    monkeypatch.setattr(sessions_mod, "DB_PATH", db_path)
    await sessions_mod.init_db()
    
    # Create a test session
    session_dict = await sessions_mod.create_session()
    session_id = session_dict["id"]
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # First set a title
        await client.patch(
            f"/api/sessions/{session_id}",
            json={"metadata": {"title": "Some Title"}}
        )
        
        # Then clear it
        response = await client.patch(
            f"/api/sessions/{session_id}",
            json={"metadata": {"title": ""}}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["title"] == ""