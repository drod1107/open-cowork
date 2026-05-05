"""Tests for Kill-Switch Extension for Non-Shell Tools (Phase 2, Feature #4).

Verifies:
- register_tool stores handle by category
- unregister_tool removes handle
- stop_current cancels web tasks
- stop_current cancels MCP tasks
- stop_current handles unknown category with task
- stop_current clears all tool handles
- backward compat: add_shell_pid still works
"""
import asyncio
import pytest
from unittest.mock import MagicMock, patch

from backend.main import HubState


@pytest.mark.asyncio
async def test_register_tool_stores_handle_by_category():
    """Test register_tool stores handle and makes it retrievable."""
    hub = HubState()
    mock_task = asyncio.create_task(asyncio.sleep(100))
    
    hub.register_tool("web", mock_task)
    
    # Verify task is stored
    assert "web" in hub._active_tools
    assert mock_task in hub._active_tools["web"]
    
    # Cleanup
    mock_task.cancel()


@pytest.mark.asyncio
async def test_unregister_tool_removes_handle():
    """Test unregister_tool removes a specific handle from the category."""
    hub = HubState()
    mock_task = asyncio.create_task(asyncio.sleep(100))
    
    hub.register_tool("web", mock_task)
    hub.unregister_tool("web", mock_task)
    
    # Verify task removed
    assert mock_task not in hub._active_tools.get("web", [])


@pytest.mark.asyncio
async def test_stop_current_cancels_web_tasks():
    """Test stop_current cancels asyncio.Tasks registered under 'web' category."""
    hub = HubState()
    mock_task = asyncio.create_task(asyncio.sleep(100))
    
    hub.register_tool("web", mock_task)
    await hub.stop_current()
    
    # Verify task was cancelled
    assert mock_task.cancelled()


@pytest.mark.asyncio
async def test_stop_current_cancels_mcp_tasks():
    """Test stop_current cancels asyncio.Tasks registered under 'mcp' category."""
    hub = HubState()
    mock_task = asyncio.create_task(asyncio.sleep(100))
    
    hub.register_tool("mcp", mock_task)
    await hub.stop_current()
    
    # Verify task was cancelled
    assert mock_task.cancelled()


@pytest.mark.asyncio
async def test_stop_current_handles_unknown_category_with_task():
    """Test stop_current cancels Task registered under custom category."""
    hub = HubState()
    mock_task = asyncio.create_task(asyncio.sleep(100))
    
    hub.register_tool("custom-category", mock_task)
    await hub.stop_current()
    
    # Verify task was cancelled
    assert mock_task.cancelled()


@pytest.mark.asyncio
async def test_stop_current_clears_all_tool_handles():
    """Test after stop_current, all _active_tools categories are empty."""
    hub = HubState()
    task1 = asyncio.create_task(asyncio.sleep(100))
    task2 = asyncio.create_task(asyncio.sleep(100))
    
    hub.register_tool("web", task1)
    hub.register_tool("mcp", task2)
    
    await hub.stop_current()
    
    # Verify all cleared
    for category, handles in hub._active_tools.items():
        assert len(handles) == 0


def test_backward_compat_add_shell_pid_still_works():
    """Test add_shell_pid() and get_shell_pids() still work via new internal structure."""
    hub = HubState()
    
    # Use backward-compatible method
    hub.add_shell_pid(12345)
    
    # Verify via backward-compatible getter
    pids = hub.get_shell_pids()
    assert 12345 in pids
    
    # Also verify it's in new structure
    assert 12345 in hub._active_tools.get("shell", [])