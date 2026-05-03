"""Tests for stop/killswitch functionality - verifies stream and shell PIDs are killed."""

import asyncio
import os
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.asyncio


async def test_stop_kills_shell_pids(tmp_config):
    """Verify stop message kills running shell PIDs with SIGTERM first, then SIGKILL."""
    from backend.main import HubState

    hub = HubState()

    # Mock some fake PIDs
    fake_pids = [12345, 12346]

    # Mock os.kill to avoid actually killing processes
    killed_pids = []

    def mock_kill(pid, sig):
        killed_pids.append((pid, sig))

    with patch("os.kill", side_effect=mock_kill):
        # Simulate adding PIDs (normally done during tool execution)
        for pid in fake_pids:
            hub.add_shell_pid(pid)

        assert len(hub.get_shell_pids()) == 2

        # Call stop
        await hub.stop_current()

        # Verify all PIDs were killed with SIGTERM (15) first, then SIGKILL (9) if needed
        # Expected: 2 PIDs × 2 signals = 4 calls
        assert len(killed_pids) == 4, f"Expected 4 kill calls (SIGTERM + SIGKILL for each PID), got {len(killed_pids)}"

        # Each PID should get SIGTERM (15) first, then SIGKILL (9)
        # Order: (12345, 15), (12345, 9), (12346, 15), (12346, 9)
        assert (12345, 15) in killed_pids, "Expected SIGTERM (15) for PID 12345"
        assert (12345, 9) in killed_pids, "Expected SIGKILL (9) for PID 12345"
        assert (12346, 15) in killed_pids, "Expected SIGTERM (15) for PID 12346"
        assert (12346, 9) in killed_pids, "Expected SIGKILL (9) for PID 12346"

        # Verify PIDs list was cleared
        assert len(hub.get_shell_pids()) == 0


async def test_stop_cancels_agent_task(tmp_config):
    """Verify stop message cancels the current agent asyncio task."""
    from backend.main import HubState

    hub = HubState()

    # Create a fake task that runs for a while
    async def long_running():
        await asyncio.sleep(10)
        return "done"

    task = asyncio.create_task(long_running())
    hub.set_current_task(task)

    assert not task.done()

    # Call stop
    await hub.stop_current()

    # Verify task was cancelled
    assert task.done()
    assert task.cancelled()


async def test_stop_with_no_active_task(tmp_config):
    """Verify stop works gracefully when no task is running."""
    from backend.main import HubState

    hub = HubState()
    hub.set_current_task(None)

    # Should not raise
    await hub.stop_current()

    assert hub._current_task is None
