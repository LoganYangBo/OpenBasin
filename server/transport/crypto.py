"""AES-256-GCM transport envelope.

The Android agent encrypts each event payload on-device with the per-device
256-bit key before upload; the server decrypts it here. GCM gives us
confidentiality *and* authentication in one pass — a tampered ciphertext fails
to decrypt rather than yielding garbage.

Envelope wire format (JSON, all binary fields base64-encoded)::

    {
      "device_id": "pixel-8",
      "nonce":     "<base64 12 bytes>",
      "ciphertext":"<base64 ... + 16-byte GCM tag>"
    }

The Kotlin counterpart is ``android/transport/EncryptedUploader.kt``.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12  # 96-bit nonce — the GCM standard / most efficient size.
KEY_BYTES = 32  # AES-256.


class EnvelopeError(Exception):
    """Raised when an envelope cannot be decrypted or is malformed."""


def _decode_key(aes_key_b64: str) -> bytes:
    key = base64.b64decode(aes_key_b64)
    if len(key) != KEY_BYTES:
        raise EnvelopeError(f"AES key must be {KEY_BYTES} bytes, got {len(key)}")
    return key


def decrypt_envelope(envelope: dict[str, Any], aes_key_b64: str) -> dict[str, Any]:
    """Decrypt an envelope dict and return the inner JSON payload as a dict."""
    key = _decode_key(aes_key_b64)
    try:
        nonce = base64.b64decode(envelope["nonce"])
        ciphertext = base64.b64decode(envelope["ciphertext"])
    except (KeyError, ValueError) as exc:
        raise EnvelopeError(f"Malformed envelope: {exc}") from exc

    if len(nonce) != NONCE_BYTES:
        raise EnvelopeError(f"Nonce must be {NONCE_BYTES} bytes, got {len(nonce)}")

    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, associated_data=None)
    except InvalidTag as exc:
        raise EnvelopeError("Authentication failed — wrong key or tampered payload") from exc

    try:
        return json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EnvelopeError(f"Decrypted payload is not valid JSON: {exc}") from exc


def encrypt_envelope(payload: dict[str, Any], aes_key_b64: str, device_id: str) -> dict[str, Any]:
    """Encrypt a payload into an envelope.

    Provided primarily for tests and for non-Android sources written in Python;
    the canonical encryptor in production is the Android agent. The nonce is
    drawn from ``os.urandom`` via :class:`AESGCM`.
    """
    import os

    key = _decode_key(aes_key_b64)
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(
        nonce, json.dumps(payload).encode("utf-8"), associated_data=None
    )
    return {
        "device_id": device_id,
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }
