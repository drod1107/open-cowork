"""Build ToolSpec objects from our concrete tool implementations.

Keeping this separate from agent.py keeps the agent loop generic and
testable with fake tools.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..agent import ToolSpec
from ..permissions import PermissionGate
from . import coding as coding_tool
from . import computer as computer_tool
from . import shell as shell_tool
from . import web as web_tool
from .browser import PlaywrightMCPClient


def build_registry(
    gate: PermissionGate,
    *,
    working_dir: str | Path = ".",
    enable_computer: bool = True,
    enable_browser: bool = True,
) -> dict[str, ToolSpec]:
    reg: dict[str, ToolSpec] = {}

    # shell
    async def _shell(args: dict[str, Any]) -> dict[str, Any]:
        res = await shell_tool.run_shell(
            args["command"], gate=gate, working_dir=str(working_dir)
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

    # web.search
    async def _search(args: dict[str, Any]) -> dict[str, Any]:
        res = await web_tool.search_web(args["query"], gate=gate)
        return res.to_dict()

    reg["search_web"] = ToolSpec(
        name="search_web",
        description="Search the web via DuckDuckGo and return the top results.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        handler=_search,
    )

    # web.fetch
    async def _fetch(args: dict[str, Any]) -> dict[str, Any]:
        res = await web_tool.fetch_url(args["url"], gate=gate)
        return res.to_dict()

    reg["fetch_url"] = ToolSpec(
        name="fetch_url",
        description="Fetch the body of a URL (text). Use after search_web.",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        handler=_fetch,
    )

    # coding tools
    async def _read(args: dict[str, Any]) -> dict[str, Any]:
        return (await coding_tool.read_file(args["path"])).to_dict()

    async def _write(args: dict[str, Any]) -> dict[str, Any]:
        return (
            await coding_tool.write_file(args["path"], args["content"], gate=gate)
        ).to_dict()

    async def _edit(args: dict[str, Any]) -> dict[str, Any]:
        return (
            await coding_tool.edit_file(
                args["path"], args["old"], args["new"], gate=gate
            )
        ).to_dict()

    async def _git_status(_args: dict[str, Any]) -> dict[str, Any]:
        return (
            await coding_tool.git_status(gate=gate, working_dir=str(working_dir))
        ).to_dict()

    async def _git_commit(args: dict[str, Any]) -> dict[str, Any]:
        return (
            await coding_tool.git_commit(
                args["message"],
                gate=gate,
                working_dir=str(working_dir),
                add_all=bool(args.get("add_all", False)),
            )
        ).to_dict()

    reg["read_file"] = ToolSpec(
        "read_file",
        "Read a text file from disk.",
        {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        _read,
    )
    reg["write_file"] = ToolSpec(
        "write_file",
        "Write a text file to disk (gated).",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        _write,
    )
    reg["edit_file"] = ToolSpec(
        "edit_file",
        "Edit a file by replacing the first occurrence of `old` with `new` (gated, diff previewed).",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old": {"type": "string"},
                "new": {"type": "string"},
            },
            "required": ["path", "old", "new"],
        },
        _edit,
    )
    reg["git_status"] = ToolSpec(
        "git_status", "Get git status of the working dir.",
        {"type": "object", "properties": {}}, _git_status,
    )
    reg["git_commit"] = ToolSpec(
        "git_commit",
        "Create a git commit (gated).",
        {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "add_all": {"type": "boolean", "default": False},
            },
            "required": ["message"],
        },
        _git_commit,
    )

    # computer use (optional)
    if enable_computer:
        comp = computer_tool.Computer(gate=gate)

        async def _shot(_args: dict[str, Any]) -> dict[str, Any]:
            return (await comp.screenshot()).to_dict()

        async def _click(args: dict[str, Any]) -> dict[str, Any]:
            return (
                await comp.click(int(args["x"]), int(args["y"]), args.get("button", "left"))
            ).to_dict()

        async def _type(args: dict[str, Any]) -> dict[str, Any]:
            return (await comp.type_text(args["text"])).to_dict()

        async def _key(args: dict[str, Any]) -> dict[str, Any]:
            return (await comp.key(args["key"])).to_dict()

        async def _scroll(args: dict[str, Any]) -> dict[str, Any]:
            return (
                await comp.scroll(
                    int(args["x"]),
                    int(args["y"]),
                    args.get("direction", "down"),
                    int(args.get("amount", 3)),
                )
            ).to_dict()

        reg["screenshot"] = ToolSpec(
            "screenshot", "Capture a screenshot of the current desktop.",
            {"type": "object", "properties": {}}, _shot,
        )
        reg["click"] = ToolSpec(
            "click", "Click at an (x,y) pixel coordinate.",
            {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "button": {"type": "string", "enum": ["left", "middle", "right"]},
                },
                "required": ["x", "y"],
            },
            _click,
        )
        reg["type_text"] = ToolSpec(
            "type_text", "Type a string via the keyboard.",
            {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            _type,
        )
        reg["key"] = ToolSpec(
            "key", "Send a keypress / key combo (e.g. 'ctrl+s').",
            {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
            _key,
        )
        reg["scroll"] = ToolSpec(
            "scroll", "Scroll up/down/left/right at an (x,y) pixel.",
            {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "direction": {"type": "string"},
                    "amount": {"type": "integer", "default": 3},
                },
                "required": ["x", "y", "direction"],
            },
            _scroll,
        )

    # browser (MCP Playwright)
    if enable_browser:
        browser = PlaywrightMCPClient(gate=gate)

        async def _browser_action(args: dict[str, Any]) -> dict[str, Any]:
            return (
                await browser.call(args["action"], args.get("params") or {})
            ).to_dict()

        reg["browser"] = ToolSpec(
            "browser",
            "Call a Playwright MCP browser action (goto, click, type, screenshot, content). Params as declared by @playwright/mcp.",
            {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "params": {"type": "object"},
                },
                "required": ["action"],
            },
            _browser_action,
        )

    return reg
