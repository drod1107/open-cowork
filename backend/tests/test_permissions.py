import pytest

from backend.permissions import PermissionGate


pytestmark = pytest.mark.asyncio


async def test_allowlist_match_auto_approves(tmp_config):
    gate = PermissionGate(config_path=tmp_config)
    result = await gate.check("shell", "echo hello")
    assert result.allowed is True
    assert "Pre-approved" in result.reason


async def test_blocklist_match_auto_denies(tmp_config):
    gate = PermissionGate(config_path=tmp_config)
    result = await gate.check("shell", "rm -rf /something")
    assert result.allowed is False


async def test_ask_prompter_approve(tmp_config):
    async def prompter(req):
        assert req.category == "shell"
        return {"decision": "approve"}

    gate = PermissionGate(prompter=prompter, config_path=tmp_config)
    result = await gate.check("shell", "git push")
    assert result.allowed is True


async def test_ask_prompter_deny(tmp_config):
    async def prompter(req):
        return {"decision": "deny"}

    gate = PermissionGate(prompter=prompter, config_path=tmp_config)
    result = await gate.check("shell", "weird-command --danger")
    assert result.allowed is False


async def test_approve_always_persists(tmp_config):
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


async def test_web_search_allow_default(tmp_config):
    gate = PermissionGate(config_path=tmp_config)
    result = await gate.check("web", "search")
    assert result.allowed is True


async def test_timeout_auto_denies(tmp_config):
    async def slow(req):
        import asyncio

        await asyncio.sleep(5)
        return {"decision": "approve"}

    gate = PermissionGate(prompter=slow, config_path=tmp_config, timeout_seconds=0.05)
    result = await gate.check("shell", "never-gonna-finish")
    assert result.allowed is False
    assert "timed out" in result.reason
