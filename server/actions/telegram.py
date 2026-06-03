"""Telegram action — send a templated message via the Bot API."""

from __future__ import annotations

import httpx

from server.actions.base import ActionContext, ActionError, BaseAction, register, render


@register("telegram")
class TelegramAction(BaseAction):
    async def run(self, ctx: ActionContext) -> str:
        token = self.config.get("bot_token") or self.secrets.get("telegram_bot_token")
        chat_id = self.config.get("chat_id") or self.secrets.get("telegram_chat_id")
        if not token or not chat_id:
            raise ActionError("telegram action requires bot_token and chat_id")

        message = render(self.config.get("message", "{raw_content}"), ctx)
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ActionError(f"Telegram send failed: {exc}") from exc
        return f"sent to chat {chat_id}"
