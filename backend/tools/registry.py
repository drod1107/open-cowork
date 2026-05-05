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
from . import web as web_tool


def build_registry(
    gate: PermissionGate,
    *,
    working_dir: str | Path = ".",
    on_shell_pid: Callable[[int], None] | None = None,
    on_web_task: Callable[[Any], None] | None = None,
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

    async def _fetch_url(args: dict[str, Any]) -> dict[str, Any]:
        return await web_tool.fetch_url(args["url"], gate=gate, on_web_task=on_web_task)

    reg["fetch_url"] = ToolSpec(
        name="fetch_url",
        description="Fetch a URL and return its text content. Only text-based content-types are supported (HTML, JSON, plain text, etc.).",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string", "description": "URL to fetch"}},
            "required": ["url"],
        },
        handler=_fetch_url,
    )

    async def _search_web(args: dict[str, Any]) -> dict[str, Any]:
        return await web_tool.search_web(args["query"], gate=gate, on_web_task=on_web_task)

    reg["search_web"] = ToolSpec(
        name="search_web",
        description="Search the web using DuckDuckGo and return top results with titles, URLs, and snippets.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query"}},
            "required": ["query"],
        },
        handler=_search_web,
    )

    return reg
