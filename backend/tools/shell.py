"""Shell tool.

Runs a command in a user-chosen working dir after the permission gate
approves it. Returns a dict so the frontend can render stdout/stderr/exit
code separately.
"""
from __future__ import annotations

import asyncio
import logging
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..permissions import PermissionGate
from ..config_loader import load_config
from .spillover import maybe_spillover

logger = logging.getLogger(__name__)


@dataclass
class ShellResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    allowed: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "allowed": self.allowed,
            "reason": self.reason,
        }


async def run_shell(
    command: str,
    *,
    gate: PermissionGate,
    working_dir: str | Path = ".",
    timeout: float = 120.0,
    config_path: str | Path | None = None,
    on_pid: Callable[[int], None] | None = None,
) -> ShellResult:
    """Run `command` after checking tool toggle and permission gate."""
    cfg = load_config(config_path or getattr(gate, "_config_path", None))
    if not cfg.get("tools", {}).get("shell", True):
        logger.info("shell blocked by config toggle: %s", command)
        return ShellResult(command, -1, "", "Shell tool is disabled in config", False, "Shell tool is disabled in config")

    permission = await gate.check(
        "shell", command, description=f"Run shell command: {command}"
    )
    if not permission.allowed:
        logger.info("shell blocked by permission gate: %s — %s", command, permission.reason)
        return ShellResult(command, -1, "", permission.reason, False, permission.reason)

    logger.info("shell executing: %s (cwd=%s)", command, working_dir)
    proc = await asyncio.create_subprocess_shell(
        command,
        cwd=str(Path(working_dir).expanduser().resolve()),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    if on_pid is not None:
        on_pid(proc.pid)
        logger.debug("shell PID %d registered", proc.pid)

    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        logger.warning("shell timed out after %ss: %s", timeout, command)
        return ShellResult(command, -1, "", f"timed out after {timeout}s", True, "timeout")
    except asyncio.CancelledError:
        proc.kill()
        await proc.wait()
        logger.warning("shell cancelled (user stop): %s (PID %d)", command, proc.pid)
        raise

    exit_code = proc.returncode if proc.returncode is not None else -1
    stdout = maybe_spillover(stdout_b.decode(errors="replace"), prefix="shell_stdout")
    stderr = maybe_spillover(stderr_b.decode(errors="replace"), prefix="shell_stderr")
    logger.info("shell done: %s exit=%d stdout=%d bytes stderr=%d bytes", command, exit_code, len(stdout_b), len(stderr_b))
    return ShellResult(
        command=command,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        allowed=True,
        reason=permission.reason,
    )


def tokenize(command: str) -> list[str]:
    """Safe split helper for callers that need argv style."""
    return shlex.split(command)
