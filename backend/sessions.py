"""Session persistence backed by SQLite.

Each session stores its message history as a JSON array in the `sessions`
table.  Metadata (title, etc.) lives in a JSON column alongside timestamps.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

DB_PATH = Path(__file__).parent / "db" / "sessions.db"


async def init_db(db_path: Path | None = None) -> None:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id        TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                messages  TEXT NOT NULL DEFAULT '[]',
                metadata  TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        await db.commit()


async def create_session(db_path: Path | None = None) -> dict[str, Any]:
    path = db_path or DB_PATH
    sid = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "INSERT INTO sessions (id, created_at, updated_at) VALUES (?, ?, ?)",
            (sid, now, now),
        )
        await db.commit()
    return {"id": sid, "created_at": now, "updated_at": now, "metadata": {}, "messages": []}


async def append_message(
    session_id: str,
    role: str,
    content: str,
    db_path: Path | None = None,
) -> None:
    path = db_path or DB_PATH
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(path) as db:
        row = await db.execute_fetchall(
            "SELECT messages FROM sessions WHERE id = ?", (session_id,)
        )
        if not row:
            return
        messages = json.loads(row[0][0])
        messages.append({"role": role, "content": content})
        await db.execute(
            "UPDATE sessions SET messages = ?, updated_at = ? WHERE id = ?",
            (json.dumps(messages), now, session_id),
        )
        await db.commit()


async def get_session(session_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    path = db_path or DB_PATH
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "messages": json.loads(row["messages"]),
            "metadata": json.loads(row["metadata"]),
        }


async def list_sessions(db_path: Path | None = None) -> list[dict[str, Any]]:
    path = db_path or DB_PATH
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, created_at, updated_at, metadata FROM sessions ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
    return [
        {
            "id": r["id"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "metadata": json.loads(r["metadata"]),
        }
        for r in rows
    ]


async def delete_session(session_id: str, db_path: Path | None = None) -> bool:
    path = db_path or DB_PATH
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await db.commit()
        return cursor.rowcount > 0


async def update_session_metadata(
    session_id: str,
    metadata: dict[str, Any],
    db_path: Path | None = None,
) -> bool:
    path = db_path or DB_PATH
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(path) as db:
        row = await db.execute_fetchall(
            "SELECT metadata FROM sessions WHERE id = ?", (session_id,)
        )
        if not row:
            return False
        existing = json.loads(row[0][0])
        existing.update(metadata)
        cursor = await db.execute(
            "UPDATE sessions SET metadata = ?, updated_at = ? WHERE id = ?",
            (json.dumps(existing), now, session_id),
        )
        await db.commit()
        return cursor.rowcount > 0
