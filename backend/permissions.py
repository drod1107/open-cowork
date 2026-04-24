"""Permission gate engine.

Every tool call flows through `PermissionGate.check(...)` before execution:

1. If the action matches a pre-approved pattern in config -> execute silently.
2. If it matches a hard-blocked pattern -> deny immediately.
3. Otherwise emit a permission request over WebSocket; wait async for the
   user's response. `approve-always` / `deny-always` mutate the config file.

The gate is transport-agnostic: it depends on a callable `prompter` that
returns an awaitable dict like `{"decision": "approve"}`. In production the
prompter is backed by the WebSocket hub; in tests it is a simple mock.
"""
from __future__ import annotations

import asyncio
import fnmatch
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable

from .config_loader import load_config, save_config


class Decision(str, Enum):
    APPROVE = "approve"
    DENY = "deny"
    APPROVE_ALWAYS = "approve-always"
    DENY_ALWAYS = "deny-always"


@dataclass
class PermissionRequest:
    category: str
    action: str
    description: str
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass
class PermissionResult:
    allowed: bool
    reason: str
    persisted: bool = False


# Maps a category name to the permission sub-dict key and list keys we care about.
_CATEGORY_LIST_KEYS: dict[str, tuple[str, str]] = {
    "shell": ("allowed_commands", "blocked_commands"),
    "filesystem": ("allowed_dirs", "blocked_dirs"),
}

# Categories whose default flag lives under `permissions.<category>.default`.
_DEFAULT_CATEGORIES = {"shell", "filesystem", "browser", "computer_use", "coding"}


def _matches_any(patterns: list[str], value: str) -> bool:
    return any(fnmatch.fnmatch(value, p) for p in patterns)


class PermissionGate:
    """Async permission gate used by every tool."""

    def __init__(
        self,
        prompter: Callable[[PermissionRequest], Awaitable[dict[str, Any]]] | None = None,
        *,
        config_path: Path | str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._prompter = prompter
        self._config_path = config_path
        self._timeout = timeout_seconds
        self._lock = asyncio.Lock()

    def set_prompter(
        self, prompter: Callable[[PermissionRequest], Awaitable[dict[str, Any]]]
    ) -> None:
        self._prompter = prompter

    # ---------------------------------------------------------------- helpers
    def _get_permissions(self) -> dict[str, Any]:
        cfg = load_config(self._config_path)
        return cfg.get("permissions", {})

    def _lookup_default(self, perms: dict[str, Any], category: str, action: str) -> str:
        """Return 'ask' | 'allow' | 'deny' for this category/action."""
        sub = perms.get(category, {})
        if category == "web":
            # web has per-action defaults (search / fetch) not a generic default.
            return sub.get(action, "ask")
        if category in _DEFAULT_CATEGORIES:
            return sub.get("default", "ask")
        return "ask"

    # ---------------------------------------------------------------- check
    async def check(
        self,
        category: str,
        action: str,
        *,
        description: str | None = None,
    ) -> PermissionResult:
        perms = self._get_permissions()
        sub = perms.get(category, {})

        # 1) explicit blocklist
        blocked_key = _CATEGORY_LIST_KEYS.get(category, (None, None))[1]
        if blocked_key:
            blocked = sub.get(blocked_key, []) or []
            if _matches_any(blocked, action):
                return PermissionResult(False, f"Blocked by config pattern in {category}.{blocked_key}")

        # 2) explicit allowlist
        allowed_key = _CATEGORY_LIST_KEYS.get(category, (None, None))[0]
        if allowed_key:
            allowed = sub.get(allowed_key, []) or []
            if _matches_any(allowed, action):
                return PermissionResult(True, "Pre-approved in config")

        # 3) category default
        default = self._lookup_default(perms, category, action)
        if default == "allow":
            return PermissionResult(True, f"Allowed by {category} default")
        if default == "deny":
            return PermissionResult(False, f"Denied by {category} default")

        # 4) ask the user
        if self._prompter is None:
            return PermissionResult(False, "No interactive prompter configured")

        req = PermissionRequest(
            category=category,
            action=action,
            description=description or action,
        )
        try:
            async with self._lock:
                response = await asyncio.wait_for(self._prompter(req), timeout=self._timeout)
        except asyncio.TimeoutError:
            return PermissionResult(False, "Permission request timed out")

        decision = Decision(response.get("decision", Decision.DENY))
        if decision is Decision.APPROVE:
            return PermissionResult(True, "User approved")
        if decision is Decision.DENY:
            return PermissionResult(False, "User denied")
        if decision is Decision.APPROVE_ALWAYS:
            self._persist(category, action, allow=True)
            return PermissionResult(True, "User approved (persisted)", persisted=True)
        # DENY_ALWAYS
        self._persist(category, action, allow=False)
        return PermissionResult(False, "User denied (persisted)", persisted=True)

    # ---------------------------------------------------------------- persist
    def _persist(self, category: str, action: str, *, allow: bool) -> None:
        cfg = load_config(self._config_path)
        perms = cfg.setdefault("permissions", {}).setdefault(category, {})
        allowed_key, blocked_key = _CATEGORY_LIST_KEYS.get(category, (None, None))
        key = allowed_key if allow else blocked_key
        if not key:
            # Categories without list support (browser, computer_use, coding, web)
            # persist as a flip of the default.
            perms["default"] = "allow" if allow else "deny"
        else:
            arr = perms.setdefault(key, [])
            if action not in arr:
                arr.append(action)
        save_config(cfg, self._config_path)
