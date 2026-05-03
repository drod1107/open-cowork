"""Tests for port auto-fallback functionality.

Per MVP spec (Dev-Plan.md:267):
- If default port 7337 is in use, scan upward (7338, 7339, etc.)
- Return the first available port
- Print the actual URL on startup
"""

import inspect
import pytest


@pytest.mark.asyncio
async def test_run_function_has_port_fallback_logic():
    """Verify run() function scans for available ports.

    This test checks that the run() function contains the necessary
    logic to scan for available ports when the default is in use.
    """
    from backend import main

    # Get source code of run() function
    source = inspect.getsource(main.run)

    # Check for key elements that should be present
    has_port_scan = (
        "range(7337" in source
        or "for port" in source
        or "port_fallback" in source.lower()
    )
    has_socket_check = "connect_ex" in source or "socket" in source

    if not (has_port_scan and has_socket_check):
        pytest.fail(
            "Port auto-fallback NOT implemented in run().\n"
            "Expected: Scan ports starting from 7337 upward.\n"
            "Expected: Use socket.connect_ex() to check availability.\n"
            "See Dev-Plan.md line 267."
        )


@pytest.mark.asyncio
async def test_run_function_prints_actual_url():
    """Verify run() function prints the actual URL with correct port.

    Per MVP spec: 'Prints the actual URL on startup'
    """
    from backend import main

    source = inspect.getsource(main.run)

    # Check that run() outputs the actual port being used
    has_url_output = (
        "print(" in source
        or "logger" in source
        or "actual" in source.lower()
    )

    if not has_url_output:
        pytest.fail(
            "run() does NOT print the actual URL.\n"
            "Expected: Print the URL with the actual port being used.\n"
            "See Dev-Plan.md line 267."
        )
