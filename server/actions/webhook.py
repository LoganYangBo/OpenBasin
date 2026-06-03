"""Webhook action — POST the extracted data (plus event metadata) as JSON."""

from __future__ import annotations

from typing import Any

import httpx

from server.actions.base import ActionContext, ActionError, BaseAction, register, render


@register("webhook")
class WebhookAction(BaseAction):
    async def run(self, ctx: ActionContext) -> str:
        url = self.config.get("url")
        if not url:
            raise ActionError("webhook action requires a url")

        # Render any ${VAR}-substituted header values' {field} placeholders too.
        headers: dict[str, str] = {
            k: render(str(v), ctx) for k, v in (self.config.get("headers") or {}).items()
        }
        headers.setdefault("Content-Type", "application/json")

        body: dict[str, Any] = {
            "event": ctx.event.model_dump(mode="json"),
            "fields": ctx.fields,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=body, headers=headers)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ActionError(f"Webhook POST failed: {exc}") from exc
        return f"POST {url} -> {resp.status_code}"
