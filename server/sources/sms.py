"""SMS source — captured on Android via a ``READ_SMS`` ``BroadcastReceiver``."""

from __future__ import annotations

from typing import Any

from server.models import SignalEvent, SignalType
from server.sources.base import BaseSource, SourceError


class SmsSource(BaseSource):
    signal_type = SignalType.SMS

    def normalize(self, payload: dict[str, Any], device_id: str) -> SignalEvent:
        body = payload.get("body") or payload.get("raw_content")
        if not body:
            raise SourceError("SMS payload missing 'body'")
        return SignalEvent(
            event_id=self._event_id(payload),
            device_id=device_id,
            signal_type=SignalType.SMS,
            source_app=payload.get("source_app"),  # e.g. com.google.android.apps.messaging
            raw_content=body,
            sender=payload.get("sender") or payload.get("address"),
            timestamp=self._timestamp(payload),
            content_hash=payload.get("content_hash", ""),
        )
