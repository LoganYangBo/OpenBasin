"""Request/response bodies for the device-facing API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Envelope(BaseModel):
    """AES-256-GCM transport envelope uploaded by the Android agent."""

    device_id: str
    nonce: str = Field(..., description="base64 12-byte GCM nonce")
    ciphertext: str = Field(..., description="base64 ciphertext + 16-byte tag")


class PlainEvent(BaseModel):
    """Unencrypted event body.

    Accepted only on the local/test ingest route. The inner shape is whatever
    the matching source expects (e.g. SMS: ``body``/``sender``), plus a
    ``signal_type`` discriminator.
    """

    signal_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    pipelines: int
    events_stored: int
    devices: int


class ReloadResponse(BaseModel):
    reloaded: bool
    pipelines: int
    detail: str | None = None
