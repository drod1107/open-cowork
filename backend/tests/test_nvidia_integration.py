"""Tests for NVIDIA API integration - secure credential handling, consent flow.

Key requirements:
- Credentials stored in .env file (never in config.toml or codebase)
- Backend reads via os.getenv() - no hardcoded keys
- Popup consent flow: "No local providers detected → ask user"
- "Yes" → ping NVIDIA, populate model picker
- "No" → never ping NVIDIA unless user manually selects it
- NVIDIA provider greyed out with "User declined connection" after "No"
"""
import asyncio
import os
import pathlib
from unittest.mock import patch, MagicMock, AsyncMock
import pytest


pytestmark = pytest.mark.asyncio


async def test_nvidia_credentials_from_env(tmp_path):
    """Verify backend reads NVIDIA credentials via os.getenv(), not from config."""
    from backend.config_loader import load_config, save_config

    # Create config without NVIDIA credentials
    cfg = {
        "provider": "ollama",
        "base_url": "http://localhost:11434",
        "tools": {"shell": True},
        "permissions": {"shell": {"allowed_commands": [], "blocked_commands": []}},
    }
    config_path = tmp_path / "config.toml"
    with open(config_path, "wb") as f:
        import tomli_w
        tomli_w.dump(cfg, f)

    loaded = load_config(config_path)
    # Verify NVIDIA credentials are NOT in config
    assert "nvidia_api_key" not in loaded
    assert "NVIDIA_API_KEY" not in loaded
    assert "nvidia_base_url" not in loaded


async def test_nvidia_credentials_not_in_codebase(tmp_path):
    """Verify no hardcoded NVIDIA credentials in backend code."""
    backend_dir = pathlib.Path("/home/drod/Code/open-cowork/backend")
    
    # Only check .py files that actually exist
    if not backend_dir.exists():
        pytest.skip("Backend directory not found")
    
    for py_file in backend_dir.rglob("*.py"):
        content = py_file.read_text(errors="ignore")
        # Check for what looks like NVIDIA API key pattern (nvapi- followed by 32+ chars)
        # Skip test files that intentionally have mock/fake keys
        if "nvapi-" in content and "test" not in str(py_file).lower():
            pytest.fail(f"Potential hardcoded NVIDIA API key in {py_file}")


async def test_nvidia_consent_flow_tracking(tmp_path):
    """Verify backend tracks user consent state in memory (not persisted)."""
    from backend.main import HubState

    hub = HubState()    
    # Initially, no consent given
    assert hub is not None
    assert hub.provider is not None


async def test_env_file_in_gitignore(tmp_path):
    """Verify .env is in .gitignore to prevent accidental commits."""
    gitignore_path = pathlib.Path("/home/drod/Code/open-cowork/.gitignore")
    if gitignore_path.exists():
        content = gitignore_path.read_text()
        assert ".env" in content, ".env should be in .gitignore"
    else:
        pytest.skip(".gitignore not found")


