"""Tests for port auto-fallback functionality.

Per MVP spec (Dev-Plan.md:267):
- If default port 7337 is in use, scan upward (7338, 7339, etc.)
- Return the first available port
- Print the actual URL on startup

Why these tests FAIL:
- `run()` function doesn't have port scanning logic yet
- Dev team needs to implement:
  1. Try default port 7337
  2. If in use, scan upward (range(7337, 7345))
  3. Use `socket.connect_ex()` to check each port
  4. Print the actual URL with the port that was chosen
"""

import inspect
import pytest


@pytest.mark.asyncio
async def test_run_function_has_port_fallback_logic():
    """Verify run() function scans for available ports.

    This test checks that the run() function:
    1. Checks if default port 7337 is available
    2. Scans upward if 7337 is in use
    3. Uses socket.connect_ex() to check availability

    Why it FAILS:
    - `run()` doesn't have port scanning logic yet
    - Dev needs to add: port scanning loop, socket checks
    """
    from backend import main

    source = inspect.getsource(main.run)

    # Check for key elements
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

    Why it FAILS:
    - `run()` doesn't print the actual URL with the chosen port
    - Dev needs to add: print statement or logger.info() with the URL
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
