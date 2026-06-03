"""Turn a raw signal into structured fields with the configured LLM.

The pipeline's ``extract.schema`` declares the fields the user wants and their
types. The extractor builds a prompt, asks the LLM to return JSON, then coerces
each field to its declared type. Type coercion is deliberate: ``"$128.50"`` from
a bank SMS becomes ``128.5`` so downstream conditions like ``amount > 100`` work.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from server.extract.llm_client import LLMClient
from server.models import SignalEvent

_DEFAULT_SYSTEM = (
    "You are a precise information-extraction engine. Given a raw message, "
    "extract exactly the requested fields and respond with ONLY a single JSON "
    "object — no prose, no markdown fences. If a field cannot be determined, "
    "use null. Infer fields described as inferred (e.g. category) from context."
)

_TYPE_ALIASES = {
    "str": str,
    "string": str,
    "text": str,
    "float": float,
    "number": float,
    "int": int,
    "integer": int,
    "bool": bool,
    "boolean": bool,
    "datetime": "datetime",
}


class ExtractionError(Exception):
    pass


def _coerce(value: Any, declared: str) -> Any:
    if value is None:
        return None
    target = _TYPE_ALIASES.get(declared.lower().strip(), str)
    try:
        if target is str:
            return str(value)
        if target is bool:
            if isinstance(value, str):
                return value.strip().lower() in {"true", "yes", "1"}
            return bool(value)
        if target in (int, float):
            if isinstance(value, str):
                # Strip currency symbols, thousands separators, whitespace.
                cleaned = re.sub(r"[^0-9.\-]", "", value)
                if not any(ch.isdigit() for ch in cleaned):
                    return None  # nothing numeric to parse → leave as null
                value = cleaned
            return target(float(value))
        if target == "datetime":
            if isinstance(value, str):
                return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
            return value
    except (ValueError, TypeError):
        # A field that won't coerce becomes null rather than failing the pipeline.
        return None
    return value


def _extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of an LLM response, tolerating fences."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"LLM did not return valid JSON: {text[:200]!r}") from exc


class Extractor:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def build_prompt(
        self, event: SignalEvent, schema: dict[str, str], instructions: str = ""
    ) -> str:
        fields = "\n".join(f"  - {name}: {typ}" for name, typ in schema.items())
        extra = f"\nAdditional guidance:\n{instructions}\n" if instructions else ""
        return (
            f"Signal type: {event.signal_type.value}\n"
            f"From: {event.sender or 'unknown'}\n"
            f"App/source: {event.source_app or 'unknown'}\n"
            f"--- raw message ---\n{event.raw_content}\n--- end ---\n"
            f"{extra}\n"
            f"Extract these fields and return JSON with exactly these keys:\n{fields}"
        )

    async def extract(
        self,
        event: SignalEvent,
        schema: dict[str, str],
        instructions: str = "",
        system: str = _DEFAULT_SYSTEM,
    ) -> dict[str, Any]:
        """Run extraction and return a dict of coerced fields keyed by schema."""
        if not schema:
            return {}
        prompt = self.build_prompt(event, schema, instructions)
        raw = await self.llm.complete(system, prompt)
        parsed = _extract_json(raw)
        return {name: _coerce(parsed.get(name), typ) for name, typ in schema.items()}
