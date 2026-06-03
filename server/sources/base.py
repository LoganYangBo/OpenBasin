"""``BaseSource`` interface and registry."""

from __future__ import annotations

import abc
import uuid
from datetime import UTC, datetime
from typing import Any

from server.models import SignalEvent, SignalType


class SourceError(Exception):
    """Raised when a payload cannot be normalized into a SignalEvent."""


class BaseSource(abc.ABC):
    """Normalize a raw device payload into a :class:`SignalEvent`.

    Subclasses declare which :class:`SignalType` they handle and implement
    :meth:`normalize`. Keep them stateless — one instance is reused across
    events.
    """

    signal_type: SignalType

    @abc.abstractmethod
    def normalize(self, payload: dict[str, Any], device_id: str) -> SignalEvent:
        ...

    # Helpers shared by concrete sources -----------------------------------

    @staticmethod
    def _event_id(payload: dict[str, Any]) -> str:
        # Honor a device-supplied id (lets the agent dedup retries), else mint one.
        return str(payload.get("event_id") or uuid.uuid4())

    @staticmethod
    def _timestamp(payload: dict[str, Any]) -> datetime:
        ts = payload.get("timestamp")
        if ts is None:
            return datetime.now(UTC)
        if isinstance(ts, (int, float)):
            # Epoch milliseconds (Android) or seconds.
            seconds = ts / 1000 if ts > 1e11 else ts
            return datetime.fromtimestamp(seconds, tz=UTC)
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts)
            except ValueError:
                return datetime.now(UTC)
        return datetime.now(UTC)


_REGISTRY: dict[str, BaseSource] = {}


def register_source(source: BaseSource) -> None:
    _REGISTRY[source.signal_type.value] = source


def get_source(signal_type: str) -> BaseSource:
    try:
        return _REGISTRY[signal_type]
    except KeyError as exc:
        raise SourceError(f"No source registered for signal_type={signal_type!r}") from exc
