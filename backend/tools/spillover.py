"""Spillover storage for large tool outputs.

When a tool result exceeds a configurable threshold, the full output is
written to a file in backend/db/spillover/ and a compact reference is
returned in the conversation context instead.

The `read_chunk` tool lets the agent page through spillover data in
manageable pieces.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

SPILLOVER_DIR = Path(__file__).parent.parent / "db" / "spillover"

DEFAULT_THRESHOLD = 4096  # 4 KB


def _ensure_dir() -> None:
    SPILLOVER_DIR.mkdir(parents=True, exist_ok=True)


def write_spillover(content: str, *, prefix: str = "out") -> str:
    """Write content to a spillover file. Returns the file ID."""
    _ensure_dir()
    file_id = f"{prefix}_{uuid.uuid4().hex[:8]}"
    path = SPILLOVER_DIR / file_id
    path.write_text(content, encoding="utf-8")
    return file_id


def read_spillover(file_id: str, offset: int = 0, limit: int = 100) -> dict[str, Any]:
    """Read lines from a spillover file with offset/limit pagination."""
    path = SPILLOVER_DIR / file_id
    if not path.exists():
        return {"ok": False, "error": f"spillover file {file_id} not found"}
    lines = path.read_text(encoding="utf-8").splitlines()
    total = len(lines)
    selected = lines[offset : offset + limit]
    return {
        "ok": True,
        "file_id": file_id,
        "offset": offset,
        "limit": limit,
        "total_lines": total,
        "lines": selected,
    }


def format_reference(file_id: str, size_bytes: int) -> str:
    """Build the compact reference string placed in context."""
    if size_bytes >= 1024 * 1024:
        size_str = f"{size_bytes / 1024 / 1024:.1f}MB"
    elif size_bytes >= 1024:
        size_str = f"{size_bytes / 1024:.0f}KB"
    else:
        size_str = f"{size_bytes}B"
    return f"[Output: {size_str}, saved to spillover {file_id}. Use read_chunk to access.]"


def maybe_spillover(content: str, *, threshold: int = DEFAULT_THRESHOLD, prefix: str = "out") -> str:
    """If content exceeds threshold, write to spillover and return reference. Otherwise return content unchanged."""
    if len(content) > threshold:
        file_id = write_spillover(content, prefix=prefix)
        return format_reference(file_id, len(content))
    return content
