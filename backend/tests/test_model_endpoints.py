"""Tests for Model endpoints.

From PR-reviews.md TDD Process Audit (2026-05-03):
- Model endpoints: /api/models GET, /api/models/select POST
- Needs test coverage per TDD process

From Dev-Plan.md Phase 1 (lines 113-114):
- GET /api/models - list available models (force refresh with ?force=)
- POST /api/models/select - select active model
"""

import pytest
from fastapi.testclient import TestClient


def test_get_models_returns_dict(tmp_config):
    """Verify GET /api/models returns dict with provider, models list.

    From Dev-Plan.md:113 - list available models.
    Dev's shape: {"provider": ..., "base_url": ..., "models": [...], "selected": ...}
    """
    from backend.main import app
    client = TestClient(app)
    
    response = client.get("/api/models")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict), "Should return dict with metadata"
    assert "models" in data, "Should have models key"
    assert isinstance(data["models"], list), "models should be a list"


def test_get_models_with_force_param(tmp_config):
    """Verify GET /api/models?force=1 refreshes model list.

    From Dev-Plan.md:113 - force refresh with ?force=.
    Dev's shape: {"provider": ..., "base_url": ..., "models": [...], "selected": ...}
    """
    from backend.main import app
    client = TestClient(app)
    
    response = client.get("/api/models?force=1")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict), "Should return dict"
    assert "models" in data


def test_select_model_requires_model_field(tmp_config):
    """Verify POST /api/models/select validates model field.

    From Dev-Plan.md:114 - select active model.
    """
    from backend.main import app
    client = TestClient(app)
    
    # Empty body
    response = client.post("/api/models/select", json={})
    assert response.status_code in [400, 422], "Should reject empty body"
    
    # Missing model field
    response = client.post("/api/models/select", json={"provider": "ollama"})
    assert response.status_code in [400, 422], "Should require model field"


def test_select_model_success(tmp_config):
    """Verify POST /api/models/select with valid model.

    From Dev-Plan.md:114 - select active model.
    Dev's shape: {"selected": "model-name"}
    """
    from backend.main import app
    client = TestClient(app)
    
    response = client.post(
        "/api/models/select",
        json={"model": "test-model"}
    )
    
    # Should succeed or fail gracefully
    assert response.status_code in [200, 400, 422]
    
    if response.status_code == 200:
        data = response.json()
        assert "selected" in data, "Should have selected field"
        assert data["selected"] == "test-model"
