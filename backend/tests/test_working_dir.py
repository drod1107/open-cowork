"""Tests for Working Directory Setting UI feature (Phase 2, Feature #2).

Verifies:
- GET /api/config/working_dir returns config value
- GET resolves "." to absolute CWD path
- PATCH /api/config/working_dir updates config
- PATCH rejects nonexistent paths (400)
- PATCH rejects file paths (400)
- PATCH validates required field (422)
"""
import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from backend.config_loader import load_config, save_config


client = TestClient(app)


@pytest.fixture
def clean_config(tmp_path):
    """Create a clean config for testing."""
    config = {
        "providers": {"ollama": {"type": "ollama", "base_url": "http://localhost:11434"}},
        "permissions": {},
        "runtime": {"working_dir": "."},
    }
    config_path = tmp_path / "config.toml"
    save_config(config, config_path)
    return config_path


def test_get_working_dir_returns_config_value(clean_config, monkeypatch):
    """Test GET /api/config/working_dir returns the value from config.toml."""
    from backend import config_loader
    monkeypatch.setattr(config_loader, "DEFAULT_CONFIG_PATH", clean_config)

    response = client.get("/api/config/working_dir")
    assert response.status_code == 200
    data = response.json()
    assert "working_dir" in data
    # Should resolve "." to absolute path
    assert Path(data["working_dir"]).is_absolute()


def test_get_working_dir_resolves_dot_to_cwd(clean_config, monkeypatch):
    """Test when config has '.', GET returns absolute path of process CWD."""
    from backend import config_loader
    monkeypatch.setattr(config_loader, "DEFAULT_CONFIG_PATH", clean_config)

    response = client.get("/api/config/working_dir")
    assert response.status_code == 200
    data = response.json()
    
    # Should resolve to current working directory
    expected_cwd = str(Path(".").resolve())
    assert data["working_dir"] == expected_cwd


def test_patch_working_dir_updates_config(clean_config, monkeypatch):
    """Test PATCH /api/config/working_dir with valid dir updates config.toml and returns resolved path."""
    from backend import config_loader
    monkeypatch.setattr(config_loader, "DEFAULT_CONFIG_PATH", clean_config)

    # Use tmp_path as valid directory
    test_path = str(clean_config.parent / "test_dir")
    os.makedirs(test_path, exist_ok=True)
    
    response = client.patch(
        "/api/config/working_dir",
        json={"working_dir": test_path}
    )
    assert response.status_code == 200
    data = response.json()
    assert "working_dir" in data
    assert Path(data["working_dir"]).is_absolute()
    
    # Verify config was updated
    cfg = load_config(clean_config)
    assert cfg["runtime"]["working_dir"] == test_path


def test_patch_working_dir_rejects_nonexistent_path(clean_config, monkeypatch):
    """Test PATCH with path that doesn't exist returns 400."""
    from backend import config_loader
    monkeypatch.setattr(config_loader, "DEFAULT_CONFIG_PATH", clean_config)

    response = client.patch(
        "/api/config/working_dir",
        json={"working_dir": "/nonexistent/path/that/does/not/exist"}
    )
    assert response.status_code == 400


def test_patch_working_dir_rejects_file_path(clean_config, monkeypatch):
    """Test PATCH with path to a file (not directory) returns 400."""
    from backend import config_loader
    monkeypatch.setattr(config_loader, "DEFAULT_CONFIG_PATH", clean_config)
    
    # Create a file in tmp_path
    test_file = clean_config.parent / "test_file.txt"
    test_file.write_text("test")
    
    response = client.patch(
        "/api/config/working_dir",
        json={"working_dir": str(test_file)}
    )
    assert response.status_code == 400


def test_patch_working_dir_rejects_missing_field(clean_config, monkeypatch):
    """Test PATCH with empty body or no working_dir field returns 422."""
    from backend import config_loader
    monkeypatch.setattr(config_loader, "DEFAULT_CONFIG_PATH", clean_config)

    # Empty body
    response = client.patch("/api/config/working_dir", json={})
    assert response.status_code == 422
    
    # No working_dir field
    response = client.patch(
        "/api/config/working_dir",
        json={"other_field": "value"}
    )
    assert response.status_code == 422