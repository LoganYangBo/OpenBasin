import base64
import secrets

import pytest

from server.transport import EnvelopeError, decrypt_envelope, encrypt_envelope


def _key() -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode()


def test_encrypt_decrypt_roundtrip():
    key = _key()
    payload = {"signal_type": "sms", "body": "Charged $12.50 at Cafe"}
    envelope = encrypt_envelope(payload, key, device_id="pixel-8")
    assert envelope["device_id"] == "pixel-8"
    out = decrypt_envelope(envelope, key)
    assert out == payload


def test_wrong_key_fails_authentication():
    payload = {"signal_type": "sms", "body": "hi"}
    envelope = encrypt_envelope(payload, _key(), device_id="d")
    with pytest.raises(EnvelopeError):
        decrypt_envelope(envelope, _key())  # different key


def test_tampered_ciphertext_rejected():
    key = _key()
    envelope = encrypt_envelope({"signal_type": "sms", "body": "hi"}, key, device_id="d")
    raw = bytearray(base64.b64decode(envelope["ciphertext"]))
    raw[0] ^= 0xFF
    envelope["ciphertext"] = base64.b64encode(bytes(raw)).decode()
    with pytest.raises(EnvelopeError):
        decrypt_envelope(envelope, key)


def test_bad_key_length():
    short_key = base64.b64encode(b"too short").decode()
    with pytest.raises(EnvelopeError):
        encrypt_envelope({}, short_key, device_id="d")
