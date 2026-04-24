import pytest

from backend.config_loader import load_config, save_config
from backend.permissions import PermissionGate
from backend.tools import coding


pytestmark = pytest.mark.asyncio


def _allow_coding(tmp_config):
    cfg = load_config(tmp_config)
    cfg["permissions"]["coding"]["default"] = "allow"
    save_config(cfg, tmp_config)


async def test_read_missing(tmp_path):
    res = await coding.read_file(str(tmp_path / "nope"))
    assert res.ok is False


async def test_write_and_read_roundtrip(tmp_path, tmp_config):
    _allow_coding(tmp_config)
    gate = PermissionGate(config_path=tmp_config)
    path = tmp_path / "hello.txt"
    w = await coding.write_file(str(path), "hello", gate=gate)
    assert w.ok is True
    r = await coding.read_file(str(path))
    assert r.data == "hello"


async def test_edit_file_applies_diff(tmp_path, tmp_config):
    _allow_coding(tmp_config)
    gate = PermissionGate(config_path=tmp_config)
    path = tmp_path / "f.py"
    path.write_text("value = 1\n")
    r = await coding.edit_file(str(path), "value = 1", "value = 2", gate=gate)
    assert r.ok is True
    assert path.read_text() == "value = 2\n"
    assert "diff" in r.data


async def test_edit_file_missing_old(tmp_path, tmp_config):
    _allow_coding(tmp_config)
    gate = PermissionGate(config_path=tmp_config)
    path = tmp_path / "f.py"
    path.write_text("foo\n")
    r = await coding.edit_file(str(path), "nothere", "x", gate=gate)
    assert r.ok is False
