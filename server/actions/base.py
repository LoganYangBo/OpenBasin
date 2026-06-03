"""``BaseAction`` interface, the ``{field}`` templating helper, and registry."""

from __future__ import annotations

import abc
import string
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from server.models import SignalEvent


@dataclass
class ActionContext:
    """Everything an action might template against.

    ``fields`` are the LLM-extracted values; ``event`` is the original signal.
    The two are merged for interpolation, with extracted fields taking
    precedence so ``{merchant}`` resolves to the extracted merchant.
    """

    event: SignalEvent
    fields: dict[str, Any] = field(default_factory=dict)

    def as_mapping(self) -> dict[str, Any]:
        merged: dict[str, Any] = {
            "event_id": self.event.event_id,
            "device_id": self.event.device_id,
            "signal_type": self.event.signal_type.value,
            "source_app": self.event.source_app or "",
            "sender": self.event.sender or "",
            "raw_content": self.event.raw_content,
            "timestamp": self.event.timestamp.isoformat(),
        }
        merged.update(self.fields)
        return merged


class _SafeFormatter(string.Formatter):
    """Leave unknown ``{placeholders}`` intact instead of raising KeyError."""

    def get_value(self, key, args, kwargs):
        if isinstance(key, str):
            return kwargs.get(key, "{" + key + "}")
        return super().get_value(key, args, kwargs)


_FORMATTER = _SafeFormatter()


def render(template: str, ctx: ActionContext) -> str:
    """Interpolate ``{field}`` placeholders from the action context."""
    return _FORMATTER.format(template, **ctx.as_mapping())


class ActionError(Exception):
    pass


class BaseAction(abc.ABC):
    """Execute one side effect for a matched, extracted event.

    Concrete actions are constructed from their YAML config dict and run once
    per matching event. Implementations should be idempotent where possible and
    must raise :class:`ActionError` on failure so the engine can log it without
    aborting other actions.
    """

    type: str

    def __init__(self, config: dict[str, Any], secrets: dict[str, str] | None = None) -> None:
        self.config = config
        self.secrets = secrets or {}

    @abc.abstractmethod
    async def run(self, ctx: ActionContext) -> str:
        """Perform the side effect; return a short human-readable detail string."""
        ...


_REGISTRY: dict[str, type[BaseAction]] = {}


def register(action_type: str) -> Callable[[type[BaseAction]], type[BaseAction]]:
    def deco(cls: type[BaseAction]) -> type[BaseAction]:
        cls.type = action_type
        _REGISTRY[action_type] = cls
        return cls

    return deco


def build_action(config: dict[str, Any], secrets: dict[str, str] | None = None) -> BaseAction:
    action_type = config.get("type")
    if action_type not in _REGISTRY:
        raise ActionError(
            f"Unknown action type {action_type!r}. Known: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[action_type](config, secrets)
