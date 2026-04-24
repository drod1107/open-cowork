"""Computer-use tool.

Implements an `AsyncComputer`-like surface for KDE Plasma on Wayland and X11.
The runtime backend is detected at startup. Each action is permission-gated.
If the selected model is not vision-capable, callers should warn the user —
`requires_vision=True` is set on every action.
"""
from __future__ import annotations

import asyncio
import base64
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..permissions import PermissionGate


def _detect_session() -> str:
    """Return 'wayland' | 'x11' | 'windows' | 'darwin' | 'unknown'."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "darwin"
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"


@dataclass
class ComputerResult:
    action: str
    ok: bool
    data: Any
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "ok": self.ok, "data": self.data, "reason": self.reason}


class Computer:
    """Async wrapper around xdotool / ydotool / spectacle / scrot."""

    def __init__(self, *, gate: PermissionGate, session: str | None = None) -> None:
        self.gate = gate
        self.session = session or _detect_session()

    async def _run(self, *argv: str) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr_b = await proc.communicate()
        return (
            proc.returncode if proc.returncode is not None else -1,
            stdout_b.decode(errors="replace"),
            stderr_b.decode(errors="replace"),
        )

    async def _gate(self, action: str, desc: str) -> bool:
        result = await self.gate.check("computer_use", action, description=desc)
        return result.allowed

    # ------------------------------------------------------------ screenshot
    async def screenshot(self) -> ComputerResult:
        if not await self._gate("screenshot", "Take a screenshot"):
            return ComputerResult("screenshot", False, None, "denied")

        tmp = Path(tempfile.gettempdir()) / "opencowork-shot.png"
        if tmp.exists():
            tmp.unlink()

        if self.session == "wayland" and shutil.which("spectacle"):
            code, _out, err = await self._run(
                "spectacle", "--background", "--nonotify", "-f", "-o", str(tmp)
            )
        elif self.session == "x11" and shutil.which("scrot"):
            code, _out, err = await self._run("scrot", str(tmp))
        else:
            # Pure-Python fallback via `mss` (works on all platforms).
            try:
                import mss  # type: ignore

                with mss.mss() as sct:
                    sct.shot(output=str(tmp))
                code, err = 0, ""
            except Exception as exc:  # pragma: no cover
                return ComputerResult("screenshot", False, None, f"no backend: {exc}")

        if code != 0 or not tmp.exists():
            return ComputerResult("screenshot", False, None, f"exit={code} {err}")

        encoded = base64.b64encode(tmp.read_bytes()).decode()
        return ComputerResult(
            "screenshot",
            True,
            {"image_base64": encoded, "mime": "image/png"},
            "ok",
        )

    # ------------------------------------------------------------ input
    async def click(self, x: int, y: int, button: str = "left") -> ComputerResult:
        if not await self._gate("click", f"Click {button} at ({x},{y})"):
            return ComputerResult("click", False, None, "denied")
        btn_map = {"left": "1", "middle": "2", "right": "3"}
        btn = btn_map.get(button, "1")
        if self.session == "wayland" and shutil.which("ydotool"):
            # ydotool expects relative/absolute moves via mousemove then click.
            await self._run("ydotool", "mousemove", "--absolute", "--", str(x), str(y))
            code, _o, err = await self._run("ydotool", "click", btn)
        elif shutil.which("xdotool"):
            code, _o, err = await self._run(
                "xdotool", "mousemove", str(x), str(y), "click", btn
            )
        else:
            return ComputerResult("click", False, None, "no input backend installed")
        ok = code == 0
        return ComputerResult("click", ok, {"x": x, "y": y, "button": button}, err if not ok else "ok")

    async def type_text(self, text: str) -> ComputerResult:
        if not await self._gate("type", f"Type: {text[:40]}"):
            return ComputerResult("type", False, None, "denied")
        if self.session == "wayland" and shutil.which("ydotool"):
            code, _o, err = await self._run("ydotool", "type", "--", text)
        elif shutil.which("xdotool"):
            code, _o, err = await self._run("xdotool", "type", "--", text)
        else:
            return ComputerResult("type", False, None, "no input backend installed")
        ok = code == 0
        return ComputerResult("type", ok, {"text": text}, err if not ok else "ok")

    async def key(self, key_combo: str) -> ComputerResult:
        if not await self._gate("key", f"Key: {key_combo}"):
            return ComputerResult("key", False, None, "denied")
        if self.session == "wayland" and shutil.which("ydotool"):
            code, _o, err = await self._run("ydotool", "key", key_combo)
        elif shutil.which("xdotool"):
            code, _o, err = await self._run("xdotool", "key", key_combo)
        else:
            return ComputerResult("key", False, None, "no input backend installed")
        ok = code == 0
        return ComputerResult("key", ok, {"key": key_combo}, err if not ok else "ok")

    async def scroll(self, x: int, y: int, direction: str, amount: int = 3) -> ComputerResult:
        if not await self._gate("scroll", f"Scroll {direction} at ({x},{y})"):
            return ComputerResult("scroll", False, None, "denied")
        xdo_button = {"up": "4", "down": "5", "left": "6", "right": "7"}.get(direction, "5")
        if shutil.which("xdotool"):
            code, _o, err = await self._run(
                "xdotool", "mousemove", str(x), str(y), "click", "--repeat", str(amount), xdo_button
            )
            ok = code == 0
            return ComputerResult("scroll", ok, {"direction": direction}, err if not ok else "ok")
        return ComputerResult("scroll", False, None, "no scroll backend installed")
