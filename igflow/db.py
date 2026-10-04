from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# briefed -> assembling -> review -> approved -> published
#                 \-> failed          \-> rejected
STATUSES = ("briefed", "assembling", "review", "approved", "rejected", "published", "failed")
_UPDATABLE = {"status", "scheduled_at", "final_path", "ig_media_id", "error", "published_at"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                format TEXT NOT NULL,
                status TEXT NOT NULL,
                brief TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                scheduled_at TEXT,
                published_at TEXT,
                final_path TEXT,
                ig_media_id TEXT,
                error TEXT
            )"""
        )
        self.db.commit()

    def create(self, post_id: str, fmt: str, brief: dict) -> None:
        ts = now_iso()
        self.db.execute(
            "INSERT INTO posts (id, format, status, brief, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (post_id, fmt, "briefed", json.dumps(brief), ts, ts),
        )
        self.db.commit()

    def get(self, post_id: str) -> dict:
        row = self.db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if row is None:
            raise KeyError(post_id)
        return self._row(row)

    def list(self, status: str | None = None) -> list[dict]:
        if status:
            rows = self.db.execute("SELECT * FROM posts WHERE status = ? ORDER BY created_at", (status,))
        else:
            rows = self.db.execute("SELECT * FROM posts ORDER BY created_at")
        return [self._row(r) for r in rows.fetchall()]

    def update(self, post_id: str, **fields) -> None:
        bad = set(fields) - _UPDATABLE
        if bad:
            raise ValueError(f"cannot update {bad}")
        if fields.get("status") and fields["status"] not in STATUSES:
            raise ValueError(f"unknown status {fields['status']}")
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.db.execute(
            f"UPDATE posts SET {cols}, updated_at = ? WHERE id = ?",
            (*fields.values(), now_iso(), post_id),
        )
        self.db.commit()

    def recent_briefs(self, n: int = 20) -> list[dict]:
        rows = self.db.execute("SELECT brief FROM posts ORDER BY created_at DESC LIMIT ?", (n,)).fetchall()
        return [json.loads(r["brief"]) for r in rows]

    def published_since(self, since_iso: str) -> int:
        row = self.db.execute(
            "SELECT COUNT(*) AS c FROM posts WHERE status = 'published' AND published_at >= ?", (since_iso,)
        ).fetchone()
        return row["c"]

    @staticmethod
    def _row(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["brief"] = json.loads(d["brief"])
        return d
