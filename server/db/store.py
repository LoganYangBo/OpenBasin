"""SQLite-backed event store.

Deduplication is part of the data model: ``event_id`` is the primary key and
``content_hash`` carries a UNIQUE index. The same physical signal arriving twice
(retried upload, SMS + notification of the same message) is rejected at insert
time rather than flowing into the pipeline twice.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from server.models import SignalEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id      TEXT PRIMARY KEY,
    device_id     TEXT NOT NULL,
    signal_type   TEXT NOT NULL,
    source_app    TEXT,
    raw_content   TEXT NOT NULL,
    sender        TEXT,
    timestamp     TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    received_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (content_hash)
);
CREATE INDEX IF NOT EXISTS idx_events_device ON events (device_id);
CREATE INDEX IF NOT EXISTS idx_events_type   ON events (signal_type);

CREATE TABLE IF NOT EXISTS action_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     TEXT NOT NULL,
    pipeline     TEXT NOT NULL,
    action_type  TEXT NOT NULL,
    ok           INTEGER NOT NULL,
    detail       TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_action_event ON action_log (event_id);
"""


class EventStore:
    """Thread-safe SQLite wrapper. A single connection guarded by a lock is
    plenty for the ingest volume of one person's device(s)."""

    def __init__(self, path: str = "/data/openbasin.db") -> None:
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- ingestion ---------------------------------------------------------

    def is_duplicate(self, event: SignalEvent) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM events WHERE event_id = ? OR content_hash = ? LIMIT 1",
                (event.event_id, event.content_hash),
            ).fetchone()
        return row is not None

    def insert(self, event: SignalEvent) -> bool:
        """Insert an event. Returns ``False`` if it was a duplicate (no-op)."""
        with self._lock:
            try:
                self._conn.execute(
                    """INSERT INTO events
                       (event_id, device_id, signal_type, source_app, raw_content,
                        sender, timestamp, content_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        event.event_id,
                        event.device_id,
                        event.signal_type.value,
                        event.source_app,
                        event.raw_content,
                        event.sender,
                        event.timestamp.isoformat(),
                        event.content_hash,
                    ),
                )
                self._conn.commit()
                return True
            except sqlite3.IntegrityError:
                # Duplicate event_id or content_hash — dedup at the data layer.
                self._conn.rollback()
                return False

    # -- action audit ------------------------------------------------------

    def log_action(
        self, event_id: str, pipeline: str, action_type: str, ok: bool, detail: str = ""
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO action_log (event_id, pipeline, action_type, ok, detail) "
                "VALUES (?, ?, ?, ?, ?)",
                (event_id, pipeline, action_type, 1 if ok else 0, detail),
            )
            self._conn.commit()

    # -- read / export -----------------------------------------------------

    def get(self, event_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
        return dict(row) if row else None

    def recent(self, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM events ORDER BY received_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]

    def export_jsonl(self) -> str:
        """Export every stored event as JSON Lines — you control the data."""
        return "\n".join(json.dumps(r) for r in self.recent(limit=10_000_000))

    def close(self) -> None:
        with self._lock:
            self._conn.close()
