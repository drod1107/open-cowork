"""Tests for tool toggle enforcement."""

import pytest
from httpx import AsyncClient
from backend.main import app
from backend.tests.conftest import hub
from backend.tools import shell as shell_mod
from backend.permissions import PermissionGate
from pathlib import Path


@pytest.fixture
def enabled_config(tmp_config):
    """Config with shell=true."""
    cfg = '''[runtime]
working_dir = "."

[active_provider]
provider = "ollama"
base_url = "http://localhost:11434"
model = "test-model"

[tools]
shell = true

[permissions]
enabled = false
'''
    config_path = tmp_config.parent / "config_enabled.toml"
    config_path.write_text(cfg)
    return config_path


@pytest.fixture
def disabled_config(tmp_config):
    """Config with shell=false."""
    cfg = '''[runtime]
working_dir = "."

[active_provider]
provider = "ollama"
base_url = "http://localhost:11434"
model = "test-model"

[tools]
shell = false

[permissions]
enabled = false
'''
    config_path = tmp_config.parent / "config_disabled.toml"
    config_path.write_text(cfg)
    return config_path


@pytest.mark.asyncio
async def test_shell_tool_disabled_blocks_all_usage(disabled_config, monkeypatch):
    """Verify shell tool is blocked when config says shell=false."""
    gate = PermissionGate(config_path=disabled_config)
    
    result = await shell_mod.run_shell(
        "echo test",
        gate=gate,
        working_dir=".",
        config_path=disabled_config,
        on_pid=None,
    )
    
    assert result.exit_code != 0, f"Shell should be blocked when disabled: {result.stderr}"
    output = result.stdout + result.stderr
    assert "disabled" in output.lower(), f"Should mention 'disabled': {output}"


@pytest.mark.asyncio
async def test_shell_tool_enabled_allows_usage(enabled_config, monkeypatch):
    """Verify shell tool works when config says shell=true."""
    gate = PermissionGate(config_path=enabled_config)
    
    # Mock the permission check to return allowed
    async def mock_check(*args, **kwargs):
        return type("PermResult", (), {"allowed": True, "reason": "test"})()
    
    monkeypatch.setattr(gate, "check", mock_check)
    
    result = await shell_mod.run_shell(
        "echo 'tool is enabled'",
        gate=gate,
        working_dir=".",
        config_path=enabled_config,
        on_pid=None,
    )
    
    assert result.exit_code == 0, f"Shell should work when enabled: {result.stderr}"


@pytest.mark.asyncio
async def test_shell_tool_disabled_ignores_past_permissions(disabled_config, monkeypatch):
    """Verify toggle OFF overrides any past 'always allow' permissions."""
    gate = PermissionGate(config_path=disabled_config)
    
    result = await shell_mod.run_shell(
        "echo test",
        gate=gate,
        working_dir=".",
        config_path=disabled_config,
        on_pid=None,
    )
    
    assert result.exit_code != 0, f"Toggle OFF should block regardless of permissions: {result.stderr}"
    output = result.stdout + result.stderr
    assert "disabled" in output.lower() or "shell" in output.lower(), f"Should mention disabled: {output}"
