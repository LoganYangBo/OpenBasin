"""File action — append the extracted record to a local file on the server.

Defaults to JSON Lines, which keeps the archive append-only and trivially
parseable. Stays entirely on infrastructure you control — no outbound call.
"""

from __future__ import annotations

import json
from pathlib import Path

from server.actions.base import ActionContext, ActionError, BaseAction, register, render


@register("file")
class FileAction(BaseAction):
    async def run(self, ctx: ActionContext) -> str:
        path_str = self.config.get("path")
        if not path_str:
            raise ActionError("file action requires a path")
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)

        fmt = self.config.get("format", "jsonl")
        if fmt == "jsonl":
            record = {
                "event_id": ctx.event.event_id,
                "timestamp": ctx.event.timestamp.isoformat(),
                "signal_type": ctx.event.signal_type.value,
                "sender": ctx.event.sender,
                **ctx.fields,
            }
            # When no extraction ran, keep the raw signal so the archive is still
            # meaningful. If a field already captured it, don't duplicate.
            if not ctx.fields:
                record["raw_content"] = ctx.event.raw_content
            line = json.dumps(record, ensure_ascii=False)
        else:
            # Freeform: render a user template, one line per event.
            line = render(self.config.get("template", "{raw_content}"), ctx)

        try:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            raise ActionError(f"File append failed: {exc}") from exc
        return f"appended to {path}"
