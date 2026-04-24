import pytest

from backend.permissions import PermissionGate
from backend.tools.shell import run_shell, tokenize


pytestmark = pytest.mark.asyncio


async def test_runs_allowed_command(tmp_config, tmp_path):
    gate = PermissionGate(config_path=tmp_config)
    result = await run_shell("echo hello", gate=gate, working_dir=str(tmp_path))
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert result.allowed is True


async def test_blocked_command_is_refused(tmp_config, tmp_path):
    gate = PermissionGate(config_path=tmp_config)
    result = await run_shell("rm -rf /", gate=gate, working_dir=str(tmp_path))
    assert result.allowed is False
    assert result.exit_code == -1


async def test_tokenize():
    assert tokenize("echo 'hi there'") == ["echo", "hi there"]
