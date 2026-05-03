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
from . import spillover as spillover_mod


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

    async def _read_chunk(args: dict[str, Any]) -> dict[str, Any]:
        return spillover_mod.read_spillover(
            args["file_id"],
            offset=int(args.get("offset", 0)),
            limit=int(args.get("limit", 100)),
        )

    reg["read_chunk"] = ToolSpec(
        name="read_chunk",
        description="Page through a spillover output file saved from a previous tool call. Provide file_id, offset (line number), and limit (number of lines).",
        parameters={
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "Spillover file ID from a previous tool reference"},
                "offset": {"type": "integer", "description": "Line number to start reading from (0-indexed)", "default": 0},
                "limit": {"type": "integer", "description": "Number of lines to read", "default": 100},
            },
            "required": ["file_id"],
        },
        handler=_read_chunk,
    )

    return reg
