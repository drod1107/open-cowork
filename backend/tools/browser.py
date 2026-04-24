"""Playwright MCP bridge.

Starts `@playwright/mcp` as a subprocess on first use and speaks the
stdio JSON-RPC protocol. Each browser action is permission-gated.

We deliberately keep this shim minimal: it exposes `goto`, `click`,
`type`, `screenshot`, `content`. A richer set can be added by calling
`raw_call` with any method the running MCP server advertises.
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any

from ..permissions import PermissionGate


@dataclass
class BrowserResult:
    action: str
    ok: bool
    data: Any
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "ok": self.ok, "data": self.data, "reason": self.reason}


class PlaywrightMCPClient:
    """Tiny JSON-RPC-over-stdio client for @playwright/mcp."""

    def __init__(
        self,
        *,
        gate: PermissionGate,
        command: str | None = None,
        extra_args: list[str] | None = None,
    ) -> None:
        self.gate = gate
        self._command = command or os.environ.get("PLAYWRIGHT_MCP_CMD", "npx")
        self._args = extra_args or ["-y", "@playwright/mcp@latest"]
        self._proc: asyncio.subprocess.Process | None = None
        self._seq = 0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._proc is not None:
            return
        self._proc = await asyncio.create_subprocess_exec(
            self._command,
            *self._args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # Send MCP initialize handshake.
        await self._raw_call("initialize", {"protocolVersion": "2024-11-05"})

    async def stop(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.terminate()
            await asyncio.wait_for(self._proc.wait(), timeout=5.0)
        except (asyncio.TimeoutError, ProcessLookupError):  # pragma: no cover
            pass
        self._proc = None

    async def _raw_call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        assert self._proc and self._proc.stdin and self._proc.stdout
        async with self._lock:
            self._seq += 1
            payload = {
                "jsonrpc": "2.0",
                "id": self._seq,
                "method": method,
                "params": params or {},
            }
            self._proc.stdin.write((json.dumps(payload) + "\n").encode())
            await self._proc.stdin.drain()
            line = await self._proc.stdout.readline()
            if not line:
                raise RuntimeError("Playwright MCP closed the pipe")
            return json.loads(line.decode())

    async def call(self, action: str, params: dict[str, Any] | None = None) -> BrowserResult:
        permission = await self.gate.check(
            "browser",
            action,
            description=f"Browser action: {action} {params or ''}",
        )
        if not permission.allowed:
            return BrowserResult(action, False, None, permission.reason)
        await self.start()
        try:
            resp = await self._raw_call("tools/call", {"name": action, "arguments": params or {}})
            if "error" in resp:
                return BrowserResult(action, False, resp["error"], permission.reason)
            return BrowserResult(action, True, resp.get("result"), permission.reason)
        except Exception as exc:  # pragma: no cover - defensive
            return BrowserResult(action, False, str(exc), permission.reason)
