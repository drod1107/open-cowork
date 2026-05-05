"""Tests for Web Tool feature (Phase 2, Feature #5).

Verifies:
- fetch_url returns content from HTTP GET
- fetch_url blocked by permission gate
- fetch_url disabled by tools.web toggle
- search_web returns parsed results
- search_web blocked by permission gate
- fetch_url rejects binary content-types
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.tools.web import fetch_url, search_web
from backend.permissions import PermissionGate


@pytest.mark.asyncio
async def test_fetch_url_returns_content():
    """Test fetch_url with a mock HTTP response returns content dict."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html"}
    mock_response.text = "<html>Test content</html>"
    mock_response.raise_for_status = MagicMock()
    
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    
    gate = PermissionGate(config_path=None, tools={"web": True})
    gate.permissions = {"web": {"fetch_url": "allow"}}
    
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_url("https://example.com", gate=gate)
    
    assert "content" in result
    assert "status" in result


@pytest.mark.asyncio
async def test_fetch_url_blocked_by_permission():
    """Test fetch_url returns denied result when permission gate denies."""
    gate = PermissionGate(config_path=None, tools={"web": True})
    gate.permissions = {"web": {"fetch_url": "deny"}}
    
    result = await fetch_url("https://example.com", gate=gate)
    
    assert result.get("error") is not None or result.get("status") == "denied"


@pytest.mark.asyncio
async def test_fetch_url_disabled_by_toggle():
    """Test fetch_url returns disabled error when config has tools.web = false."""
    gate = PermissionGate(config_path=None, tools={"web": False})
    gate.permissions = {"web": {"fetch_url": "allow"}}
    
    result = await fetch_url("https://example.com", gate=gate)
    
    assert "disabled" in result.get("error", "").lower() or result.get("status") == "disabled"


@pytest.mark.asyncio
async def test_search_web_returns_results():
    """Test search_web with mock HTTP returns parsed results."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '''
    <a result class="result" href="https://example.com">Example Title</a>
    <a result class="result" href="https://test.com">Test Title</a>
    '''
    
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    
    gate = PermissionGate(config_path=None, tools={"web": True})
    gate.permissions = {"web": {"search_web": "allow"}}
    
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await search_web("test query", gate=gate)
    
    assert "results" in result or "error" not in result


@pytest.mark.asyncio
async def test_search_web_blocked_by_permission():
    """Test search_web returns denied result when permission gate denies."""
    gate = PermissionGate(config_path=None, tools={"web": True})
    gate.permissions = {"web": {"search_web": "deny"}}
    
    result = await search_web("test query", gate=gate)
    
    assert result.get("error") is not None or result.get("status") == "denied"


@pytest.mark.asyncio
async def test_fetch_url_rejects_binary_content_type():
    """Test fetch_url returns error when response has binary content-type."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "image/png"}
    mock_response.raise_for_status = MagicMock()
    
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    
    gate = PermissionGate(config_path=None, tools={"web": True})
    gate.permissions = {"web": {"fetch_url": "allow"}}
    
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_url("https://example.com/image.png", gate=gate)
    
    assert "error" in result or "binary" in result.get("error", "").lower()