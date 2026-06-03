"""Pydantic models for the YAML pipeline format.

The README's "Pipeline reference" is the source of truth for this shape. A
pipeline has up to four sections executed in order: trigger → extract →
conditions → actions.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from server.models import SignalEvent


class Trigger(BaseModel):
    signal_type: str
    source_app: str | None = None
    filter: str | None = None  # simple "kw1 OR kw2" keyword pre-filter

    def matches(self, event: SignalEvent) -> bool:
        if event.signal_type.value != self.signal_type:
            return False
        if self.source_app and event.source_app != self.source_app:
            return False
        if self.filter and not _filter_matches(self.filter, event.raw_content):
            return False
        return True


class Extract(BaseModel):
    schema_: dict[str, str] = Field(default_factory=dict, alias="schema")
    prompt: str | None = None  # name of a reusable extractor prompt
    instructions: str | None = None

    model_config = {"populate_by_name": True}


class Pipeline(BaseModel):
    name: str
    trigger: Trigger
    extract: Extract = Field(default_factory=Extract)
    conditions: list[str] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)


def _filter_matches(expression: str, content: str) -> bool:
    """Evaluate a simple keyword filter against message content.

    Grammar: OR-separated groups, each an AND-separated set of keywords.
    Matching is case-insensitive substring. Example:
        "bank OR charged OR payment"  -> any keyword present
        "amazon AND refund"           -> both present
    """
    haystack = content.lower()
    for or_group in expression.split(" OR "):
        terms = [t.strip().lower() for t in or_group.split(" AND ") if t.strip()]
        if terms and all(term in haystack for term in terms):
            return True
    return False
