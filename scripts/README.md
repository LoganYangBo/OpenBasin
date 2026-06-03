# OpenBasin dev scripts & end-to-end testing

Helpers for testing the server locally **without a phone, and without WSL**. The
server is pure Python (FastAPI + SQLite) and runs natively on Windows; Docker is
only for deployment.

| Script | Purpose |
|---|---|
| `send_test_event.py` | Encrypt a signal with a device's AES key (exactly like the Android agent) and POST it to a running server. Stands in for the phone. |

## Prerequisites (once)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

A ready-to-run `config.yaml` already exists (pre-filled device token + AES key,
pointing at the offline `pipelines/dev` smoke pipeline). Regenerate the key any
time with `python -m server.cli gen-key`.

---

## Test level 1 — automated (no network, no LLM)

The full ingest chain (auth → decrypt → normalize → dedup → trigger → action) is
covered by the suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api_e2e.py -v
.\.venv\Scripts\python.exe -m pytest          # everything (33 tests)
```

---

## Test level 2 — live offline smoke test

Runs the real server and pushes a real encrypted event. No LLM key required —
`config.yaml` ships pointing at `pipelines/dev/archive-sms.yaml`, which has no
`extract.schema` and just archives every SMS to a file.

**Terminal A — start the server:**

```powershell
.\.venv\Scripts\python.exe -m server
# -> "OpenBasin ready: 1 pipelines, 1 devices"
```

**Terminal B — send a test signal:**

```powershell
.\.venv\Scripts\python.exe scripts\send_test_event.py --type sms --body "Chase charged $42 at Cafe"
```

Expected response:

```
HTTP 200
{'event_id': '...', 'accepted': True, 'duplicate': False, 'matched_pipelines': ['dev_archive_sms']}
```

**Verify:**

```powershell
type data\archive\sms.jsonl
curl http://localhost:8080/v1/events/recent -H "X-Device-Token: MBigiwqtqfHo0dbsB2wpRDDpqkb2pVMw"
```

Send the **same** body again → response shows `'duplicate': True` (dedup works).

`send_test_event.py` options:

```powershell
# Email
.\.venv\Scripts\python.exe scripts\send_test_event.py --type email --subject "Receipt" --body "Invoice #42 total $99 from Acme"
# Notification
.\.venv\Scripts\python.exe scripts\send_test_event.py --type notification --source-app com.example.bank --body "You spent $10"
# Point at a non-default server
.\.venv\Scripts\python.exe scripts\send_test_event.py --url http://localhost:8080
```

---

## Test level 3 — full chain with LLM extraction + real actions

1. In `config.yaml`, set `server.pipelines_dir` back to `pipelines`.
2. Configure an LLM:
   - **OpenAI:** `setx OPENAI_API_KEY sk-...` (reopen the shell so it loads), keep `provider: openai`.
   - **Ollama (fully offline):**
     ```yaml
     llm:
       provider: ollama
       model: llama3.2
       base_url: http://localhost:11434/v1
       api_key: ollama
     ```
3. (Optional) Fill `secrets:` with your Telegram / Firefly tokens to see those
   actions fire; otherwise they log a failure and the rest of the pipeline
   continues.
4. Restart the server and send a bank SMS:

```powershell
.\.venv\Scripts\python.exe scripts\send_test_event.py --body "Your Chase card ending 6688 was charged $128.50 at Whole Foods on 06/02."
```

The `credit_card_bookkeeping` pipeline calls your LLM to extract
`merchant / amount / category`, checks conditions, then runs its actions. Watch
the server logs for the extraction result and per-action outcome.

---

## Notes

- **WSL is not required.** Use native Windows Python for dev; use
  `docker compose up -d` (runs over Docker Desktop) for deployment. With Docker,
  the `db.path: /data/openbasin.db` Linux path in `config.example.yaml` is
  correct because it runs inside the container.
- `config.yaml`, `data/`, and `*.db` are git-ignored — your local secrets and
  event store never get committed.
- Reload pipelines without restarting:
  `.\.venv\Scripts\python.exe -m server.cli reload`
