"""Build ToolSpec objects from our concrete tool implementations.

Keeping this separate from agent.py keeps the agent loop generic and
testable with fake tools.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..agent import ToolSpec
from ..permissions import PermissionGate
from . import shell as shell_tool


def build_registry(
    gate: PermissionGate,
    *,
    working_dir: str | Path = ".",
    on_shell_pid: Callable[[int], None] | None = None,
) -> dict[str, ToolSpec]:
    reg: dict[str, ToolSpec] = {}

    async def _shell(args: dict[str, Any]) -> dict[str, Any]:
        res = await shell_tool.run_shell(
            args["command"],
            gate=gate,
            working_dir=str(working_dir),
            on_pid=on_shell_pid,
        )
        return res.to_dict()

    reg["shell"] = ToolSpec(
        name="shell",
        description="Run a shell command in the configured working directory.",
        parameters={
            "type": "object",
            "properties": {"command": {"type": "string", "description": "Shell command"}},
            "required": ["command"],
        },
        handler=_shell,
    )

    return reg
