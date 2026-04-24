import httpx
import pytest
import respx

from backend.permissions import PermissionGate
from backend.tools.web import fetch_url, search_web


pytestmark = pytest.mark.asyncio


@respx.mock
async def test_fetch_url_auto_allow(tmp_config):
    # Flip web.fetch default to allow so we don't need a prompter.
    from backend.config_loader import load_config, save_config

    cfg = load_config(tmp_config)
    cfg["permissions"]["web"]["fetch"] = "allow"
    save_config(cfg, tmp_config)

    respx.get("https://example.com/").mock(
        return_value=httpx.Response(200, text="<html>ok</html>")
    )
    gate = PermissionGate(config_path=tmp_config)
    result = await fetch_url("https://example.com/", gate=gate)
    assert result.status == 200
    assert "ok" in result.content


@respx.mock
async def test_fetch_url_denied_without_prompter(tmp_config):
    gate = PermissionGate(config_path=tmp_config)
    result = await fetch_url("https://example.com/", gate=gate)
    assert result.allowed is False


@respx.mock
async def test_search_web_parses_ddg(tmp_config):
    html_body = """
    <div class="result">
      <a class="result__a" href="https://a.example/">Alpha site</a>
      <a class="result__snippet" href="#">Alpha snippet text</a>
    </div>
    <div class="result">
      <a class="result__a" href="https://b.example/">Beta site</a>
      <a class="result__snippet" href="#">Beta snippet text</a>
    </div>
    """
    respx.get("https://duckduckgo.com/html/").mock(
        return_value=httpx.Response(200, text=html_body)
    )
    gate = PermissionGate(config_path=tmp_config)
    res = await search_web("anything", gate=gate)
    assert res.allowed is True
    assert len(res.results) == 2
    assert res.results[0]["url"] == "https://a.example/"
    assert res.results[0]["title"].startswith("Alpha")
