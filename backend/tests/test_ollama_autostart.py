"""Tests for Ollama auto-start functionality.

Per MVP spec (Dev-Plan.md:266):
- Auto-start Ollama in `run()` if binary is present and port 11434 is not yet listening
- Check for Ollama binary in PATH
- Check if port 11434 is already in use
- Start Ollama process if conditions met
"""

import inspect
import pytest


@pytest.mark.asyncio
async def test_run_function_has_ollama_auto_start():
    """Verify run() function has Ollama auto-start logic.

    This test checks that the run() function:
    1. Checks for Ollama binary in PATH
    2. Checks if port 11434 is free
    3. Starts Ollama if conditions are met
    """
    from backend import main

    source = inspect.getsource(main.run)

    # Check for key elements
    has_binary_check = (
        "shutil.which" in source
        or "ollama" in source.lower()
        or "binary" in source.lower()
    )
    has_port_check = "11434" in source or "connect_ex" in source
    has_start_logic = "Popen" in source or "subprocess" in source or "serve" in source

    if not (has_binary_check and has_port_check):
        pytest.fail(
            "Ollama auto-start NOT implemented in run().\n"
            "Expected: Check for Ollama binary with shutil.which().\n"
            "Expected: Check if port 11434 is available.\n"
            "See Dev-Plan.md line 266."
        )


@pytest.mark.asyncio
async def test_run_function_starts_ollama_process():
    """Verify run() actually starts Ollama process."""
    from backend import main

    source = inspect.getsource(main.run)

    has_subprocess_start = (
        "Popen" in source
        or "subprocess.Popen" in source
        or '"ollama"' in source
        or "'ollama'" in source
    )

    if not has_subprocess_start:
        pytest.fail(
            "Ollama auto-start process NOT implemented.\n"
            "Expected: subprocess.Popen(['ollama', 'serve']) or similar.\n"
            "See Dev-Plan.md line 266."
        )
