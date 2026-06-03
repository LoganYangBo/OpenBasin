"""End-to-end ingest test through the FastAPI app — no network, no LLM.

Uses a pipeline with an empty extract schema (so the engine never calls the
LLM) and a `file` action writing to a temp path. Exercises auth, the encrypted
envelope route, source normalization, dedup, trigger matching, and action exec.
"""

import base64
import json
import secrets

import pytest
from fastapi.testclient import TestClient

from server.api.app import create_app
from server.config import Config
from server.transport import encrypt_envelope


@pytest.fixture()
def client(tmp_path):
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    # A pipeline with no schema → no LLM call; file action archives the raw signal.
    archive = tmp_path / "sms.jsonl"
    pipelines_dir = tmp_path / "pipelines"
    pipelines_dir.mkdir()
    (pipelines_dir / "p.yaml").write_text(
        "name: archive_sms\n"
        "trigger:\n  signal_type: sms\n  filter: \"charged\"\n"
        "actions:\n  - type: file\n    path: " + json.dumps(str(archive)) + "\n",
        encoding="utf-8",
    )

    config = Config.model_validate(
        {
            "server": {"pipelines_dir": str(pipelines_dir)},
            "db": {"path": ":memory:"},
            "devices": [{"device_id": "pixel-8", "token": "tok-123", "aes_key": key}],
        }
    )
    app = create_app(config)
    with TestClient(app) as c:
        c.aes_key = key  # type: ignore[attr-defined]
        c.archive = archive  # type: ignore[attr-defined]
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["pipelines"] == 1
    assert body["devices"] == 1


def test_rejects_unknown_token(client):
    env = encrypt_envelope({"signal_type": "sms", "body": "x"}, client.aes_key, "pixel-8")
    r = client.post("/v1/events", json=env, headers={"X-Device-Token": "wrong"})
    assert r.status_code == 401


def test_encrypted_ingest_fires_pipeline(client):
    payload = {"signal_type": "sms", "body": "Card charged $20 at Cafe", "sender": "Bank"}
    env = encrypt_envelope(payload, client.aes_key, "pixel-8")
    r = client.post("/v1/events", json=env, headers={"X-Device-Token": "tok-123"})
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] and not body["duplicate"]
    assert body["matched_pipelines"] == ["archive_sms"]
    # Action wrote the archive line.
    assert "Cafe" in client.archive.read_text()


def test_dedup_on_resend(client):
    payload = {"signal_type": "sms", "body": "Card charged $99", "sender": "Bank",
               "event_id": "fixed-1"}
    env = encrypt_envelope(payload, client.aes_key, "pixel-8")
    headers = {"X-Device-Token": "tok-123"}
    first = client.post("/v1/events", json=env, headers=headers).json()
    second = client.post("/v1/events", json=env, headers=headers).json()
    assert first["duplicate"] is False
    assert second["duplicate"] is True


def test_envelope_device_mismatch_rejected(client):
    env = encrypt_envelope({"signal_type": "sms", "body": "x"}, client.aes_key, "someone-else")
    r = client.post("/v1/events", json=env, headers={"X-Device-Token": "tok-123"})
    assert r.status_code == 403
