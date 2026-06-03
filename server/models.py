"""The central data contract.

Every signal from every source — SMS, email, app notification — is normalized
into a single :class:`SignalEvent` *before* it reaches the pipeline engine. The
pipeline only ever sees ``SignalEvent``; sources differ, the contract does not.

``event_id`` and ``content_hash`` exist specifically for deduplication and are
part of the data model, not bolted on afterward.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SignalType(StrEnum):
    SMS = "sms"
    EMAIL = "email"
    NOTIFICATION = "notification"


class SignalEvent(BaseModel):
    """A single normalized signal. Immutable once constructed."""

    event_id: str = Field(..., description="Globally unique — used for deduplication.")
    device_id: str
    signal_type: SignalType
    source_app: str | None = Field(
        default=None, description="Android package name (notifications) or source identifier."
    )
    raw_content: str = Field(..., description="Original, untouched message content.")
    sender: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str = Field(default="", description="Dedup key — derived if not supplied.")

    def model_post_init(self, __context) -> None:  # noqa: D401
        # Derive a stable content hash when the source did not provide one, so
        # dedup works regardless of which agent produced the event.
        if not self.content_hash:
            object.__setattr__(self, "content_hash", self.compute_content_hash())

    def compute_content_hash(self) -> str:
        """Stable hash over the fields that define "the same signal"."""
        parts = [
            self.device_id,
            self.signal_type.value,
            self.source_app or "",
            self.sender or "",
            self.raw_content,
        ]
        return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()


class IngestResult(BaseModel):
    """Returned to the device after an event is received."""

    event_id: str
    accepted: bool
    duplicate: bool = False
    matched_pipelines: list[str] = Field(default_factory=list)
    detail: str | None = None
