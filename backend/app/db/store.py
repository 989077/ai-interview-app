"""SQLite storage for interview sessions (Python standard library, nothing to install).

One row per interview. The full session is kept as JSON in `data`; the columns
next to it exist so the history list can be read without opening every session.
The file path comes from DATABASE_PATH (default: data/interviews.db).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()  # SQLite allows one writer at a time; keep it simple and safe

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    role          TEXT NOT NULL,
    level         TEXT NOT NULL,
    n_questions   INTEGER NOT NULL,
    answered      INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL,
    overall_score INTEGER,
    data          TEXT NOT NULL
)
"""


def db_path() -> Path:
    return Path(os.getenv("DATABASE_PATH", "data/interviews.db"))


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_session(
    *,
    session_id: str,
    role: str,
    level: str,
    n_questions: int,
    answered: int,
    status: str,
    overall_score: int | None,
    data: dict[str, Any],
) -> None:
    now = _now()
    with _LOCK:
        conn = _connect()
        try:
            with conn:  # one transaction: either the whole row is saved or none of it
                conn.execute(
                    """
                    INSERT INTO sessions
                        (id, created_at, updated_at, role, level, n_questions,
                         answered, status, overall_score, data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        updated_at = excluded.updated_at,
                        answered = excluded.answered,
                        status = excluded.status,
                        overall_score = excluded.overall_score,
                        data = excluded.data
                    """,
                    (
                        session_id, now, now, role, level, n_questions,
                        answered, status, overall_score, json.dumps(data),
                    ),
                )
        finally:
            conn.close()


def load_session(session_id: str) -> dict[str, Any] | None:
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute("SELECT data FROM sessions WHERE id = ?", (session_id,)).fetchone()
        finally:
            conn.close()
    return json.loads(row["data"]) if row else None


def list_sessions(limit: int = 50) -> list[dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT id, created_at, role, level, n_questions, answered, status, overall_score
                FROM sessions ORDER BY created_at DESC, rowid DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        finally:
            conn.close()
    return [dict(r) for r in rows]


def delete_session(session_id: str) -> bool:
    with _LOCK:
        conn = _connect()
        try:
            with conn:
                cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        finally:
            conn.close()
    return cur.rowcount > 0
