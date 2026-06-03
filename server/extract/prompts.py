"""Loader for community extractor prompts.

Extractor prompts are the third extension point and require *no code* — they are
plain YAML files in ``server/extract/prompts/``. A pipeline may reference one by
name via ``extract.prompt: bank_sms`` to reuse a tuned schema + instructions for
a specific app or bank.

Prompt file shape::

    name: bank_sms
    description: Generic bank transaction SMS
    instructions: |
      The amount is the charged value...
    schema:
      merchant: str
      amount: float
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

PROMPTS_DIR = Path(__file__).parent / "prompts"


@lru_cache(maxsize=1)
def _load_all() -> dict[str, dict]:
    prompts: dict[str, dict] = {}
    if not PROMPTS_DIR.exists():
        return prompts
    for path in sorted(PROMPTS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        name = data.get("name", path.stem)
        prompts[name] = data
    return prompts


def get_prompt(name: str) -> dict:
    prompts = _load_all()
    if name not in prompts:
        raise KeyError(f"Extractor prompt {name!r} not found in {PROMPTS_DIR}")
    return prompts[name]
