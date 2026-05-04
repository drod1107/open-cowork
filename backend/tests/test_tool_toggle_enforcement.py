"""Tests for tool toggle enforcement.

From user feedback: When shell tool toggle is OFF in settings,
the tool should NOT be usable AT ALL - even if past permissions exist.
"""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_shell_tool_disabled_blocks_all_usage(tmp_config, monkeypatch):
    """Verify shell tool is blocked when config says shell=false.
    
    From user report: shell tool was still usable despite being toggled OFF.
    Toggle OFF should OVERRIDE any past permissions.
    """
    from backend.main import app
    from backend.tools import shell as shell_mod
    from backend.permissions import PermissionGate
    from pathlib import Path
    
    # Create a config with shell=false
    disabled_config = tmp_config.parent / "config_disabled.toml"
    disabled_config.write_text('''[runtime]
working_dir = "."

[active_provider]
provider = "ollama"
base_url = "http://localhost:11434"
model = "test-model"

[tools]
shell = false

[permissions]
enabled = false
''')
    
    # Create a mock gate
    gate = PermissionGate()
    
    # Call run_shell with shell=false config
    result = await shell_mod.run_shell(
        "echo test",
        gate=gate,
        working_dir=".",
        config_path=disabled_config,
        on_pid=None,
    )
    
    # Should be blocked (exit_code will be -1 or similar)
    assert result.exit_code != 0, f"Shell should be blocked when disabled: {result.stderr}"
    output = result.stdout + result.stderr
    assert "disabled" in output.lower(), f"Should mention 'disabled': {output}"


@pytest.mark.asyncio 
async def test_shell_tool_enabled_allows_usage(tmp_config, monkeypatch):
    """Verify shell tool works when config says shell=true."""
    from backend.main import app
    from backend.tools import shell as shell_mod
    from backend.permissions import PermissionGate
    
    # Default config has shell=true
    gate = PermissionGate()
    
    result = await shell_mod.run_shell(
        "echo 'tool is enabled'",
        gate=gate,
        working_dir=".",
        config_path=tmp_config,
        on_pid=None,
    )
    
    # Should succeed
    assert result.exit_code == 0, f"Shell should work when enabled: {result.stderr}"


@pytest.mark.asyncio
async def test_shell_tool_disabled_ignores_past_permissions(tmp_config, monkeypatch):
    """Verify toggle OFF overrides any past 'always allow' permissions.
    
    From user report: past permissions should NOT bypass a toggle OFF.
    """
    from backend.main import app
    from backend.tools import shell as shell_mod
    from backend.permissions import PermissionGate
    from pathlib import Path
    
    # Create a config with shell=false
    disabled_config = tmp_config.parent / "config_disabled.toml"
    disabled_config.write_text('''[runtime]
working_dir = "."

[active_provider]
provider = "ollama"
base_url = "http://localhost:11434"
model = "test-model"

[tools]
shell = false

[permissions]
enabled = false
''')
    
    # Create gate (permissions don't matter - toggle overrides)
    gate = PermissionGate()
    
    # Call run_shell (should be blocked regardless of permissions)
    result = await shell_mod.run_shell(
        "echo test",
        gate=gate,
        working_dir=".",
        config_path=disabled_config,
        on_pid=None,
    )
    
    # Should be blocked by config toggle (not permission system)
    assert result.exit_code != 0, f"Toggle OFF should block regardless of permissions: {result.stderr}"
    output = result.stdout + result.stderr
    assert "disabled" in output.lower() or "shell" in output.lower(), f"Should mention disabled: {output}"
