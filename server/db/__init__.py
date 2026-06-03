"""SQLite event store with built-in deduplication."""

from server.db.store import EventStore

__all__ = ["EventStore"]
