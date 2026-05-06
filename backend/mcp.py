"""MCP server integration using the official Python SDK's ClientSessionGroup.

Reads server configs from config.toml [mcp.*] sections, connects via
ClientSessionGroup, and converts discovered tools to our ToolSpec format
with permission gate integration.

Config format (matches Claude Desktop's de facto standard):
    [mcp.filesystem]
    command = "npx"
    args = ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]

    [mcp.github]
    command = "uvx"
    args = ["mcp-server-git"]
    disabled = true
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import timedelta
from typing import Any

import mcp
from mcp import ClientSessionGroup, StdioServerParameters
from mcp.client.session_group import ClientSessionParameters
from mcp.shared.exceptions import McpError
from mcp.types import Implementation, TextContent

from .agent import ToolSpec
from .permissions import PermissionGate, PermissionResult

logger = logging.getLogger(__name__)

NAMESPACE_SEP = "_"


def _namespace(server_name: str, tool_name: str) -> str:
    return f"{server_name}{NAMESPACE_SEP}{tool_name}"


def _format_tool_result(result: mcp.CallToolResult) -> dict[str, Any]:
    parts: list[str] = []
    for item in result.content:
        if isinstance(item, TextContent):
            parts.append(item.text)
        else:
            parts.append(repr(item))
    text = "\n".join(parts) if parts else ""
    if result.isError:
        return {"output": text, "error": True}
    return {"output": text}


class MCPManager:
    def __init__(self) -> None:
        self._group: ClientSessionGroup | None = None
        self._exit_stack: contextlib.AsyncExitStack | None = None
        self._server_params: dict[str, StdioServerParameters] = {}
        self._server_status: dict[str, dict[str, Any]] = {}
        self._sessions: dict[str, mcp.ClientSession] = {}

    async def start(self, cfg: dict[str, Any]) -> None:
        mcp_cfg = cfg.get("mcp", {})
        if not mcp_cfg:
            return

        self._exit_stack = contextlib.AsyncExitStack()
        await self._exit_stack.__aenter__()

        self._group = ClientSessionGroup(
            exit_stack=self._exit_stack,
            component_name_hook=lambda name, info: _namespace(
                _sanitize(info.name), name
            ),
        )

        for name, entry in mcp_cfg.items():
            if not isinstance(entry, dict):
                continue
            if entry.get("disabled", False):
                self._server_status[name] = {"status": "disabled", "tools_count": 0}
                continue
            await self._connect_server(name, entry)

    async def _connect_server(self, name: str, entry: dict[str, Any]) -> None:
        command = entry.get("command")
        if not command:
            self._server_status[name] = {
                "status": "error",
                "error": "missing command",
                "tools_count": 0,
            }
            return

        args = entry.get("args", [])
        env = entry.get("env") or None
        params = StdioServerParameters(command=command, args=args, env=env)
        self._server_params[name] = params

        try:
            session = await self._group.connect_to_server(
                params,
                ClientSessionParameters(
                    client_info=Implementation(
                        name="opencowork", version="0.1.0"
                    ),
                    read_timeout_seconds=timedelta(seconds=30),
                ),
            )
            self._sessions[name] = session
            tools_result = await session.list_tools()
            self._server_status[name] = {
                "status": "connected",
                "tools_count": len(tools_result.tools),
            }
            logger.info("MCP server '%s' connected: %d tools", name, len(tools_result.tools))
        except Exception as exc:
            self._server_status[name] = {
                "status": "error",
                "error": str(exc),
                "tools_count": 0,
            }
            logger.warning("MCP server '%s' failed: %s", name, exc)

    async def stop(self) -> None:
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._exit_stack = None
        self._group = None
        self._server_status.clear()
        self._server_params.clear()
        self._sessions.clear()

    def get_tool_specs(self, gate: PermissionGate) -> dict[str, ToolSpec]:
        if self._group is None:
            return {}

        specs: dict[str, ToolSpec] = {}
        for namespaced_name, tool_def in self._group.tools.items():
            original_name = tool_def.name
            schema = tool_def.inputSchema
            if schema is None:
                schema = {"type": "object", "properties": {}}
            schema = {**schema, "type": "object", "additionalProperties": False}

            handler = self._make_handler(namespaced_name, gate)
            specs[namespaced_name] = ToolSpec(
                name=namespaced_name,
                description=tool_def.description or "",
                parameters=schema,
                handler=handler,
            )
        return specs

    def _make_handler(
        self, namespaced_name: str, gate: PermissionGate
    ) -> Any:
        async def _handler(args: dict[str, Any]) -> dict[str, Any]:
            result = gate.check("mcp", namespaced_name)
            if not result.allowed:
                return {"output": f"Permission denied: {result.reason}"}

            try:
                call_result = await self._group.call_tool(
                    namespaced_name, args
                )
                return _format_tool_result(call_result)
            except McpError as exc:
                return {"output": f"MCP error: {exc.error.message}", "error": True}
            except Exception as exc:
                return {"output": f"Error: {exc}", "error": True}

        return _handler

    def get_status(self) -> list[dict[str, Any]]:
        result = []
        for name, status in self._server_status.items():
            entry = {"name": name, **status}
            result.append(entry)
        return result

    async def add_server(self, name: str, config: dict[str, Any]) -> None:
        if name in self._server_params or name in self._server_status:
            raise ValueError(f"MCP server '{name}' already exists")

        self._server_params[name] = StdioServerParameters(
            command=config["command"],
            args=config.get("args", []),
            env=config.get("env"),
        )

        if config.get("disabled", False):
            self._server_status[name] = {"status": "disabled", "tools_count": 0}
            return

        if self._group is None:
            self._exit_stack = contextlib.AsyncExitStack()
            await self._exit_stack.__aenter__()
            self._group = ClientSessionGroup(
                exit_stack=self._exit_stack,
                component_name_hook=lambda n, info: _namespace(
                    _sanitize(info.name), n
                ),
            )

        await self._connect_server(name, config)

    async def remove_server(self, name: str) -> None:
        session = self._sessions.pop(name, None)
        if session is not None and self._group is not None:
            try:
                await self._group.disconnect_from_server(session)
            except Exception:
                pass
        self._server_params.pop(name, None)
        self._server_status.pop(name, None)

    async def start_server(self, name: str) -> str:
        if name not in self._server_params:
            raise ValueError(f"MCP server '{name}' not found")
        if self._group is None:
            raise RuntimeError("MCP group not initialized")

        params = self._server_params[name]
        try:
            session = await self._group.connect_to_server(
                params,
                ClientSessionParameters(
                    client_info=Implementation(
                        name="opencowork", version="0.1.0"
                    ),
                ),
            )
            self._sessions[name] = session
            tools_result = await session.list_tools()
            self._server_status[name] = {
                "status": "connected",
                "tools_count": len(tools_result.tools),
            }
            return "connected"
        except Exception as exc:
            self._server_status[name] = {
                "status": "error",
                "error": str(exc),
                "tools_count": 0,
            }
            raise

    async def stop_server(self, name: str) -> None:
        session = self._sessions.pop(name, None)
        if session is None or self._group is None:
            return
        try:
            await self._group.disconnect_from_server(session)
            self._server_status[name] = {
                "status": "disconnected",
                "tools_count": 0,
            }
        except McpError:
            self._server_status[name] = {
                "status": "disconnected",
                "tools_count": 0,
            }


def _sanitize(name: str) -> str:
    return name.replace("-", "_").replace(" ", "_").lower()
