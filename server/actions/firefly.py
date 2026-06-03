"""Firefly III action — create a withdrawal transaction.

Requires a self-hosted Firefly III instance reachable on your network. See
https://www.firefly-iii.org/ . Fields are expected from the extract schema:
``amount`` (float), ``merchant`` (str), and optionally ``currency``/``category``.
"""

from __future__ import annotations

import httpx

from server.actions.base import ActionContext, ActionError, BaseAction, register, render


@register("firefly")
class FireflyAction(BaseAction):
    async def run(self, ctx: ActionContext) -> str:
        url = (self.config.get("url") or "").rstrip("/")
        token = self.config.get("token") or self.secrets.get("firefly_token")
        account = render(self.config.get("account", ""), ctx)
        if not url or not token:
            raise ActionError("firefly action requires url and token")

        fields = ctx.fields
        amount = fields.get("amount")
        if amount is None:
            raise ActionError("firefly action requires an extracted 'amount' field")

        transaction = {
            "type": "withdrawal",
            "date": ctx.event.timestamp.date().isoformat(),
            "amount": str(abs(float(amount))),
            "description": str(fields.get("merchant") or ctx.event.raw_content[:80]),
            "source_name": account or None,
            "currency_code": fields.get("currency") or None,
            "category_name": fields.get("category") or None,
        }
        body = {"transactions": [{k: v for k, v in transaction.items() if v is not None}]}
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{url}/api/v1/transactions", json=body, headers=headers)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ActionError(f"Firefly create failed: {exc}") from exc
        return f"recorded {transaction['amount']} → {account or 'default'}"
