"""Config loader / writer for OpenCowork.

TOML is the single source of truth. All reads go through `load_config`;
mutations (e.g. "approve-always" from the permission UI) go through
`save_config` which atomically rewrites the file. A lightweight in-memory
cache is refreshed on every `load_config` call so tests and the UI stay
consistent.
"""
from __future__ import annotations

import copy
from pathlib import Path
from threading import RLock
from typing import Any

try:  # Python 3.11+
    import tomllib as _toml_read  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    import tomli as _toml_read  # type: ignore

import tomli_w

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "config.toml"

_lock = RLock()


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    """Read and return the config file as a plain dict."""
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    with _lock:
        with open(p, "rb") as f:
            data = _toml_read.load(f)
    return data


def save_config(data: dict[str, Any], path: Path | str | None = None) -> None:
    """Atomically write the config dict to disk."""
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    payload = copy.deepcopy(data)
    with _lock:
        tmp = p.with_suffix(p.suffix + ".tmp")
        with open(tmp, "wb") as f:
            tomli_w.dump(payload, f)
        tmp.replace(p)


def update_permission_pattern(
    category: str,
    pattern: str,
    *,
    list_key: str = "allowed_commands",
    path: Path | str | None = None,
) -> dict[str, Any]:
    """Append a pattern to a permission allowlist. Returns the updated config."""
    cfg = load_config(path)
    perms = cfg.setdefault("permissions", {}).setdefault(category, {})
    arr = perms.setdefault(list_key, [])
    if pattern not in arr:
        arr.append(pattern)
    save_config(cfg, path)
    return cfg
