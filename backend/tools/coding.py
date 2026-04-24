"""Agentic coding tool.

Provides file read/write/edit with diff preview, patch application and
basic git ops. Every write goes through the permission gate; read is
free (files are already visible to the shell tool anyway).
"""
from __future__ import annotations

import difflib
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..permissions import PermissionGate
from .shell import run_shell


@dataclass
class CodingResult:
    action: str
    ok: bool
    data: Any
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "ok": self.ok, "data": self.data, "reason": self.reason}


async def read_file(path: str) -> CodingResult:
    p = Path(path).expanduser()
    if not p.exists():
        return CodingResult("read_file", False, None, f"no such file: {p}")
    return CodingResult("read_file", True, p.read_text(errors="replace"), "ok")


async def write_file(path: str, content: str, *, gate: PermissionGate) -> CodingResult:
    p = Path(path).expanduser()
    permission = await gate.check("coding", f"write:{p}", description=f"Write file {p}")
    if not permission.allowed:
        return CodingResult("write_file", False, None, permission.reason)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return CodingResult("write_file", True, {"path": str(p), "bytes": len(content)}, "ok")


def make_diff(a: str, b: str, *, path: str = "") -> str:
    return "".join(
        difflib.unified_diff(
            a.splitlines(keepends=True),
            b.splitlines(keepends=True),
            fromfile=f"a/{path}" if path else "a",
            tofile=f"b/{path}" if path else "b",
        )
    )


async def edit_file(
    path: str,
    old: str,
    new: str,
    *,
    gate: PermissionGate,
) -> CodingResult:
    p = Path(path).expanduser()
    if not p.exists():
        return CodingResult("edit_file", False, None, f"no such file: {p}")
    original = p.read_text()
    if old not in original:
        return CodingResult("edit_file", False, None, "old text not found")
    updated = original.replace(old, new, 1)
    diff = make_diff(original, updated, path=str(p))
    permission = await gate.check("coding", f"edit:{p}", description=f"Edit {p}\n{diff}")
    if not permission.allowed:
        return CodingResult("edit_file", False, {"diff": diff}, permission.reason)
    p.write_text(updated)
    return CodingResult("edit_file", True, {"diff": diff, "path": str(p)}, "ok")


async def git_status(*, gate: PermissionGate, working_dir: str = ".") -> CodingResult:
    res = await run_shell("git status --porcelain=v1 -b", gate=gate, working_dir=working_dir)
    return CodingResult("git_status", res.exit_code == 0, res.to_dict(), res.reason)


async def git_commit(
    message: str, *, gate: PermissionGate, working_dir: str = ".", add_all: bool = False
) -> CodingResult:
    if add_all:
        add_res = await run_shell("git add -A", gate=gate, working_dir=working_dir)
        if add_res.exit_code != 0:
            return CodingResult("git_commit", False, add_res.to_dict(), "git add failed")
    # `permissions.coding.git_commit` is an additional toggle on top of the shell gate.
    explicit = await gate.check(
        "coding", "git_commit", description=f"git commit -m {message!r}"
    )
    if not explicit.allowed:
        return CodingResult("git_commit", False, None, explicit.reason)
    cmd = f"git commit -m {shlex.quote(message)}"
    res = await run_shell(cmd, gate=gate, working_dir=working_dir)
    return CodingResult("git_commit", res.exit_code == 0, res.to_dict(), res.reason)
