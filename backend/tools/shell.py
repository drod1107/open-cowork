"""Shell tool.

Runs a command in a user-chosen working dir after the permission gate
approves it. Returns a dict so the frontend can render stdout/stderr/exit
code separately.
"""
from __future__ import annotations

import asyncio
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..permissions import PermissionGate


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
) -> ShellResult:
    """Run `command` after checking the permission gate."""
    permission = await gate.check(
        "shell", command, description=f"Run shell command: {command}"
    )
    if not permission.allowed:
        return ShellResult(command, -1, "", permission.reason, False, permission.reason)

    proc = await asyncio.create_subprocess_shell(
        command,
        cwd=str(Path(working_dir).expanduser().resolve()),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return ShellResult(command, -1, "", f"timed out after {timeout}s", True, "timeout")

    return ShellResult(
        command=command,
        exit_code=proc.returncode if proc.returncode is not None else -1,
        stdout=stdout_b.decode(errors="replace"),
        stderr=stderr_b.decode(errors="replace"),
        allowed=True,
        reason=permission.reason,
    )


def tokenize(command: str) -> list[str]:
    """Safe split helper for callers that need argv style."""
    return shlex.split(command)
