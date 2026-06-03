"""Email source — captured on-device via IMAP polling, then uploaded."""

from __future__ import annotations

from typing import Any

from server.models import SignalEvent, SignalType
from server.sources.base import BaseSource, SourceError


class EmailSource(BaseSource):
    signal_type = SignalType.EMAIL

    def normalize(self, payload: dict[str, Any], device_id: str) -> SignalEvent:
        subject = payload.get("subject", "")
        body = payload.get("body") or payload.get("raw_content")
        if not body and not subject:
            raise SourceError("Email payload missing both 'subject' and 'body'")
        # Fold subject into the content so the LLM sees it during extraction.
        raw = f"Subject: {subject}\n\n{body or ''}".strip()
        return SignalEvent(
            event_id=self._event_id(payload),
            device_id=device_id,
            signal_type=SignalType.EMAIL,
            source_app=payload.get("source_app") or payload.get("mailbox"),
            raw_content=raw,
            sender=payload.get("from") or payload.get("sender"),
            timestamp=self._timestamp(payload),
            content_hash=payload.get("content_hash", ""),
        )
