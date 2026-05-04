"""Tests for Custom Provider Form feature (Phase 2, Feature #8).

Verifies:
- POST /api/providers endpoint adds a custom provider to config
- Custom provider appears in provider list after being added
- Form validation: required fields (nickname, base_url, type)
- Duplicate provider names are rejected
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.config_loader import load_config, save_config


client = TestClient(app)


@pytest.fixture
def clean_config(tmp_path):
    """Create a clean config for testing."""
    config = {
        "providers": {
            "ollama": {"type": "ollama", "base_url": "http://localhost:11434"},
        },
        "permissions": {},
        "runtime": {},
    }
    config_path = tmp_path / "config.toml"
    save_config(config, config_path)
    return config_path


def test_post_custom_provider_adds_to_config(clean_config, monkeypatch):
    """Test that POST /api/providers adds a custom provider to config."""
    # Mock config path to use our test config
    from backend import config_loader
    monkeypatch.setattr(config_loader, "DEFAULT_CONFIG_PATH", clean_config)

    response = client.post(
        "/api/providers",
        json={
            "nickname": "my-openai",
            "base_url": "https://api.openai.com",
            "provider_type": "openai-compat",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True

    # Verify provider was added to config
    cfg = load_config(clean_config)
    assert "my-openai" in cfg["providers"]
    assert cfg["providers"]["my-openai"]["type"] == "openai-compat"
    assert cfg["providers"]["my-openai"]["base_url"] == "https://api.openai.com"


def test_post_custom_provider_validates_required_fields(clean_config, monkeypatch):
    """Test that missing required fields returns 422 validation error."""
    from backend import config_loader
    monkeypatch.setattr(config_loader, "DEFAULT_CONFIG_PATH", clean_config)

    # Missing nickname
    response = client.post(
        "/api/providers",
        json={"base_url": "https://api.openai.com", "provider_type": "openai-compat"},
    )
    assert response.status_code == 422

    # Missing base_url
    response = client.post(
        "/api/providers",
        json={"nickname": "my-openai", "provider_type": "openai-compat"},
    )
    assert response.status_code == 422

    # Missing provider_type
    response = client.post(
        "/api/providers",
        json={"nickname": "my-openai", "base_url": "https://api.openai.com"},
    )
    assert response.status_code == 422


def test_post_custom_provider_rejects_duplicate_name(clean_config, monkeypatch):
    """Test that adding a provider with existing name returns 409 conflict."""
    from backend import config_loader
    monkeypatch.setattr(config_loader, "DEFAULT_CONFIG_PATH", clean_config)

    # Add first provider
    response = client.post(
        "/api/providers",
        json={
            "nickname": "my-openai",
            "base_url": "https://api.openai.com",
            "provider_type": "openai-compat",
        },
    )
    assert response.status_code == 200

    # Try to add duplicate
    response = client.post(
        "/api/providers",
        json={
            "nickname": "my-openai",
            "base_url": "https://different-url.com",
            "provider_type": "openai-compat",
        },
    )
    assert response.status_code == 409


def test_get_providers_lists_custom_providers(clean_config, monkeypatch):
    """Test that GET /api/providers lists all providers including custom ones."""
    from backend import config_loader
    monkeypatch.setattr(config_loader, "DEFAULT_CONFIG_PATH", clean_config)

    # Add a custom provider
    client.post(
        "/api/providers",
        json={
            "nickname": "custom-ollama",
            "base_url": "http://localhost:11434",
            "provider_type": "ollama",
        },
    )

    # Get providers list - this might be a new endpoint or part of /api/config
    response = client.get("/api/config")
    assert response.status_code == 200
    config = response.json()

    assert "custom-ollama" in config.get("providers", {})


def test_delete_custom_provider_removes_from_config(clean_config, monkeypatch):
    """Test that DELETE /api/providers/{name} removes a custom provider."""
    from backend import config_loader
    monkeypatch.setattr(config_loader, "DEFAULT_CONFIG_PATH", clean_config)

    # Add a custom provider first
    client.post(
        "/api/providers",
        json={
            "nickname": "to-delete",
            "base_url": "http://localhost:11434",
            "provider_type": "ollama",
        },
    )

    # Delete it
    response = client.delete("/api/providers/to-delete")
    assert response.status_code == 200

    # Verify it's gone
    cfg = load_config(clean_config)
    assert "to-delete" not in cfg.get("providers", {})


def test_delete_builtin_provider_rejected(clean_config, monkeypatch):
    """Test that deleting a built-in provider (ollama) returns 403 forbidden."""
    from backend import config_loader
    monkeypatch.setattr(config_loader, "DEFAULT_CONFIG_PATH", clean_config)

    response = client.delete("/api/providers/ollama")
    assert response.status_code == 403
    assert "cannot delete" in response.json()["detail"].lower()