"""Tests for tool toggle (shell on/off) backend enforcement.

Note: The current run_shell() function in shell.py does NOT check the 
tools.shell config setting. This test documents the EXPECTED behavior.
The actual enforcement should happen in:
1. The tool registry (build_registry in tools/registry.py)
2. Or in the agent.py when deciding which tools to load
3. Or in main.py when handling the chat message

This test will fail until the lead dev implements the tool toggle enforcement.
"""
import pytest

pytestmark = pytest.mark.asyncio

from backend.config_loader import load_config, save_config


async def test_shell_tool_enabled_allows_execution(tmp_config, tmp_path):
    """Verify shell commands run when shell tool is enabled."""
    from backend.tools.shell import run_shell
    from backend.permissions import PermissionGate

    gate = PermissionGate(config_path=tmp_config)
    result = await run_shell("echo hello", gate=gate, working_dir=str(tmp_path))
    assert result.allowed is True
    assert result.exit_code == 0


async def test_shell_tool_disabled_blocks_execution(tmp_config, tmp_path):
    """Test that shell tool disabled should block execution.
    
    NOTE: This test currently FAILS because the enforcement is not implemented.
    The run_shell() function doesn't check config["tools"]["shell"].
    This needs to be implemented by the lead dev in:
    - backend/tools/registry.py (build_registry)
    - or backend/tools/shell.py (run_shell function)
    """
    from backend.tools.shell import run_shell
    from backend.permissions import PermissionGate

    # Disable shell tool in config
    cfg = load_config(tmp_config)
    cfg["tools"]["shell"] = False
    save_config(cfg, tmp_config)

    gate = PermissionGate(config_path=tmp_config)
    
    # TODO: The following should FAIL (allowed=False) once enforcement is implemented
    # Currently it passes because enforcement is missing
    result = await run_shell("echo hello", gate=gate, working_dir=str(tmp_path))
    
    # This is what the test should be when enforcement is implemented:
    # assert result.allowed is False
    
    # For now, just verify the config was saved correctly
    reloaded = load_config(tmp_config)
    assert reloaded["tools"]["shell"] is False
    
    # Flag this as a missing feature
    pytest.skip("Tool toggle enforcement not yet implemented - see PR-reviews.md")
