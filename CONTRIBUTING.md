# Contributing to OpenBasin

Thanks for helping. OpenBasin is built around **three extension points** — most
contributions slot into one of them without touching the core.

## Ground rules

- **No telemetry, ever.** Do not add analytics, crash reporting, or any
  phone-home. The only outbound calls allowed in the core path are to the user's
  configured LLM and action targets.
- **Local-first must stay viable.** The Ollama path must keep working fully
  offline. Never introduce a hard dependency on a cloud service in the core
  processing path.
- **Dedup is part of the data model.** Preserve `event_id` / `content_hash`.

## Dev setup

```bash
python -m venv .venv && . .venv/Scripts/activate   # or source .venv/bin/activate
pip install -e ".[dev]"

pytest                 # run the suite
pytest tests/test_conditions.py::test_numeric_comparison   # a single test
ruff check server tests
ruff format server tests
```

## Extension point 1 — a new Source

Sources normalize a raw device payload into the shared `SignalEvent`.

1. Subclass `BaseSource` in `server/sources/` and set `signal_type`.
2. Implement `normalize(payload, device_id) -> SignalEvent`.
3. Register it in `server/api/app.py::_register_sources` (and export it).

The pipeline engine never sees source-specific shapes — keep all of that inside
your source.

## Extension point 2 — a new Action

Actions perform a side effect with the extracted data. See
`server/actions/notion.py` for a complete worked example.

1. Create `server/actions/your_action.py`.
2. Subclass `BaseAction`, decorate the class with `@register("your_type")`.
3. Implement `async def run(self, ctx: ActionContext) -> str`. Use
   `render(template, ctx)` for `{field}` interpolation and raise `ActionError`
   on failure (the engine logs it without aborting sibling actions).
4. Import it in `server/actions/__init__.py` so the decorator runs.
5. Add a test under `tests/`.

## Extension point 3 — a new Extractor prompt

No code required. Add a YAML file to `server/extract/prompts/`:

```yaml
name: my_bank
description: Transaction SMS for My Bank
instructions: |
  ...guidance for the LLM...
schema:
  merchant: str
  amount: float
```

Pipelines reference it via `extract.prompt: my_bank`.

## Pull requests

- Keep changes focused and covered by tests.
- Run `pytest` and `ruff check` before opening the PR.
- If you change the device↔server crypto, update **both**
  `server/transport/crypto.py` and `android/.../EncryptedUploader.kt` — they
  must stay in lockstep.
