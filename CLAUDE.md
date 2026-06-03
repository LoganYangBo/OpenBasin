# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

The initial scaffold is **implemented**. The Python server (FastAPI + SQLite),
the pipeline engine, the LLM extraction layer, the action handlers, the Android
agent (Kotlin), Docker Compose deployment, and a passing test suite all exist.
The README's "Architecture" section now describes real code.

### Build / test / run commands

Python toolchain (server). Run from the repo root:

```bash
python -m venv .venv && . .venv/Scripts/activate    # Windows; use source .venv/bin/activate on *nix
pip install -e ".[dev]"

pytest                                               # full suite
pytest tests/test_conditions.py::test_numeric_comparison   # a single test
ruff check server tests                              # lint
ruff format server tests                             # format

python -m server                                     # run the server (reads ./config.yaml)
openbasin validate                                   # validate pipelines in config's pipelines_dir
openbasin gen-key                                    # generate a base64 AES-256 device key
openbasin reload                                     # tell a running server to reload pipelines
```

Docker (intended deployment):

```bash
cp config.example.yaml config.yaml                   # then edit it
docker compose up -d                                 # serves on :8080
```

Android agent (from `android/`):

```bash
cd android && ./gradlew assembleDebug                # APK in app/build/outputs/apk/debug/
```

### Map of the code

- `server/models.py` — the central `SignalEvent` contract.
- `server/config.py` — `config.yaml` loader with `${ENV}` interpolation.
- `server/db/` — SQLite store; dedup via `event_id` PK + `content_hash` UNIQUE.
- `server/transport/crypto.py` — AES-256-GCM envelope (mirrors the Kotlin uploader).
- `server/sources/` — `BaseSource` + sms/email/notification normalizers.
- `server/extract/` — provider-agnostic LLM client + `Extractor`; prompts in `prompts/`.
- `server/actions/` — `BaseAction` + telegram/firefly/sheet/webhook/file/notion.
- `server/pipeline/` — YAML models, loader, AST-based condition evaluator, engine.
- `server/api/app.py` — FastAPI app factory, routes, device-token auth.
- `android/` — Kotlin agent (capture + encrypted upload).

### Conventions worth preserving

- Conditions are evaluated with a strict AST allowlist (`server/pipeline/conditions.py`),
  never `eval` — keep it that way; pipeline YAML is semi-trusted input.
- Actions register themselves via the `@register("type")` decorator and are
  imported for their side effect in `server/actions/__init__.py`.
- The crypto contract is shared: changes to `server/transport/crypto.py` must be
  mirrored in `android/app/src/main/java/com/openbasin/transport/EncryptedUploader.kt`.

## Intended architecture (from README)

OpenBasin is a self-hosted personal signal-aggregation framework. The system has two halves that communicate over an encrypted device-to-server channel:

1. **Android agent** (`android/`, Kotlin) — passively captures signals and uploads them encrypted:
   - SMS via `BroadcastReceiver` (`READ_SMS`)
   - App notifications via `NotificationListenerService`
   - Email via IMAP polling
   - Transport: AES-256 encryption + per-device token auth before upload

2. **Server** (`server/`, Python — FastAPI + SQLite) — the core value layer:
   - `api/` — FastAPI endpoint receiving device events
   - `pipeline/` — YAML-defined pipeline engine
   - `extract/` — LLM extraction layer (provider-agnostic)
   - `actions/` — pluggable action handlers (Firefly, Telegram, Sheet, Webhook, File)
   - `db/` — SQLite event store with dedup

### The central data contract

Every signal from every source is normalized into one `SignalEvent` schema **before** reaching the pipeline engine. This normalization is the architectural pivot — sources differ, but the pipeline only ever sees `SignalEvent`. Fields: `event_id` (globally unique, dedup), `device_id`, `signal_type` (`sms`/`email`/`notification`), `source_app` (Android package), `raw_content`, `sender`, `timestamp`, `content_hash` (dedup key).

### The processing model

A pipeline is plain YAML with three stages, executed in order: **trigger** (match by `signal_type`/`source_app`/keyword `filter`) → **extract** (LLM fills a user-defined `schema`) → **conditions** (optional gating expressions) → **actions** (one or more). The README's "Pipeline reference" section is the source of truth for this YAML format until code defines otherwise.

### Three extension points

The design is built around three pluggable interfaces — preserve this seam structure when implementing:
- **Sources** — implement `BaseSource` (`server/sources/`)
- **Actions** — implement `BaseAction` (`server/actions/`)
- **Extractor prompts** — plain YAML, no code (`server/extract/prompts/`)

### LLM provider-agnosticism

OpenBasin bundles no model. The extraction layer targets any OpenAI-compatible `/v1/chat/completions` endpoint (OpenAI, Anthropic, Ollama, Azure). Configuration lives in `config.yaml` under `llm:` with `provider`/`model`/`api_key`/`base_url`. Do not hardcode a provider — route through this config.

## Key design constraints (non-obvious, from README)

- **No telemetry, ever.** No analytics, crash reporting, or phone-home. The privacy guarantee ("your data never leaves your infrastructure") is the product's core promise — do not add outbound calls to anything other than the user's configured LLM and action targets.
- **Local-first must stay viable.** The Ollama path must work fully offline; never introduce a hard dependency on a cloud service in the core processing path.
- **Deduplication is built into the data model**, not bolted on — `event_id` and `content_hash` exist specifically for this.
- **iOS is out of scope** (system sandbox); macOS/Windows agents are Phase 2.

## Extending the code

The scaffold is in place; new work usually means adding a source, action, or
extractor prompt (see `CONTRIBUTING.md` for the step-by-step). When you add a
dependency, update both `pyproject.toml` and `requirements.txt` (the Docker
image installs from the latter). When you add a server route or change the data
contract, add or update a test under `tests/` and keep `ruff check` clean.
