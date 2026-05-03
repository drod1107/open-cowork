import pytest
from unittest.mock import patch

from backend.permissions import PermissionGate, Decision


pytestmark = pytest.mark.asyncio


async def test_ask_prompter_approve(tmp_config):
    """Test 'this time' maps to APPROVE (one-time approval)."""
    async def prompter(req):
        assert req.category == "shell"
        # Frontend sends "this time", code maps to APPROVE
        return {"decision": "approve"}

    gate = PermissionGate(prompter=prompter, config_path=tmp_config)
    result = await gate.check("shell", "git push")
    assert result.allowed is True


async def test_ask_prompter_approve_always(tmp_config):
    """Test 'always' maps to APPROVE_ALWAYS (persists to config)."""
    async def prompter(req):
        return {"decision": "approve-always"}

    gate = PermissionGate(prompter=prompter, config_path=tmp_config)
    result = await gate.check("shell", "curl example.com")
    assert result.allowed is True
    assert result.persisted is True

    # Second call should hit the pre-approved allowlist and be auto-approved.
    gate2 = PermissionGate(config_path=tmp_config)
    result2 = await gate2.check("shell", "curl example.com")
    assert result2.allowed is True
    assert "Pre-approved" in result2.reason


async def test_ask_prompter_deny(tmp_config):
    """Test 'no' maps to DENY (one-time denial)."""
    async def prompter(req):
        return {"decision": "deny"}

    gate = PermissionGate(prompter=prompter, config_path=tmp_config)
    result = await gate.check("shell", "weird-command --danger")
    assert result.allowed is False


async def test_never_maps_to_deny_always(tmp_config):
    """Test 'never' maps to DENY_ALWAYS (adds to blocked list)."""
    async def prompter(req):
        return {"decision": "deny-always"}

    gate = PermissionGate(prompter=prompter, config_path=tmp_config)
    result = await gate.check("shell", "rm -rf /")
    assert result.allowed is False

    # Verify command was added to blocked list in config
    from backend.config_loader import load_config
    cfg = load_config(tmp_config)
    blocked = cfg["permissions"]["shell"]["blocked_commands"]
    assert any("rm -rf" in cmd for cmd in blocked)


async def test_permission_ask_default_path(tmp_config):
    """Test command not in allowed/blocked lists prompts user (ask default)."""
    gate = PermissionGate(config_path=tmp_config)
    # No prompter configured - should return "No interactive prompter configured"
    result = await gate.check("shell", "some-random-command")
    assert result.allowed is False
    assert "No interactive prompter configured" in result.reason
    async def slow(req):
        import asyncio

        await asyncio.sleep(5)
        return {"decision": "this time"}

    gate = PermissionGate(prompter=slow, config_path=tmp_config, timeout_seconds=0.05)
    result = await gate.check("shell", "never-gonna-finish")
    assert result.allowed is False
    assert "timed out" in result.reason


async def test_permission_ask_default_path(tmp_config):
    """Test command not in allowed/blocked lists prompts user (ask default)."""
    gate = PermissionGate(config_path=tmp_config)
    # No prompter configured - should return "No interactive prompter configured"
    result = await gate.check("shell", "some-random-command")
    assert result.allowed is False
    assert "No interactive prompter configured" in result.reason
