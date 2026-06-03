"""Notification source — captured via Android's ``NotificationListenerService``."""

from __future__ import annotations

from typing import Any

from server.models import SignalEvent, SignalType
from server.sources.base import BaseSource, SourceError


class NotificationSource(BaseSource):
    signal_type = SignalType.NOTIFICATION

    def normalize(self, payload: dict[str, Any], device_id: str) -> SignalEvent:
        title = payload.get("title", "")
        text = payload.get("text") or payload.get("raw_content") or ""
        if not title and not text:
            raise SourceError("Notification payload missing both 'title' and 'text'")
        raw = f"{title}\n{text}".strip()
        return SignalEvent(
            event_id=self._event_id(payload),
            device_id=device_id,
            signal_type=SignalType.NOTIFICATION,
            source_app=payload.get("source_app") or payload.get("package"),
            raw_content=raw,
            sender=payload.get("sender") or title or None,
            timestamp=self._timestamp(payload),
            content_hash=payload.get("content_hash", ""),
        )
