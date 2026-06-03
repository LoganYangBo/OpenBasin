"""Google Sheets action — append a row via the Sheets REST API.

To avoid pulling in heavyweight Google client libraries (and to keep the core
dependency-light), this uses the REST endpoint directly with an OAuth bearer
token you supply in config (a service-account access token or OAuth token). The
row is built from the extract schema's fields in declared order, unless an
explicit ``columns`` list is given.
"""

from __future__ import annotations

import httpx

from server.actions.base import ActionContext, ActionError, BaseAction, register


@register("sheet")
class SheetAction(BaseAction):
    async def run(self, ctx: ActionContext) -> str:
        spreadsheet_id = self.config.get("spreadsheet_id")
        token = self.config.get("token") or self.secrets.get("google_token")
        if not spreadsheet_id or not token:
            raise ActionError("sheet action requires spreadsheet_id and token")

        rng = self.config.get("range", "Sheet1!A:Z")
        columns = self.config.get("columns")
        mapping = ctx.as_mapping()
        if columns:
            row = [str(mapping.get(c, "")) for c in columns]
        else:
            # Default: timestamp first, then every extracted field in order.
            row = [ctx.event.timestamp.isoformat(), *[str(v) for v in ctx.fields.values()]]

        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
            f"/values/{rng}:append?valueInputOption=USER_ENTERED"
        )
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json={"values": [row]}, headers=headers)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ActionError(f"Sheets append failed: {exc}") from exc
        return f"appended row to {rng}"
