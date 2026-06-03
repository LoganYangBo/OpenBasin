"""Notion action — create a page in a database.

A worked example of the "New Action" extension point from the README. Maps
extracted fields onto Notion database properties. ``properties`` in config maps
a Notion property name to an extracted field name and a Notion type, e.g.::

    - type: notion
      database_id: ${NOTION_DB}
      token: ${NOTION_TOKEN}
      title_field: merchant
      properties:
        Amount:   { field: amount,   type: number }
        Category: { field: category, type: select }
"""

from __future__ import annotations

from typing import Any

import httpx

from server.actions.base import ActionContext, ActionError, BaseAction, register

_NOTION_VERSION = "2022-06-28"


def _prop_value(notion_type: str, value: Any) -> dict[str, Any]:
    if value is None:
        return {notion_type: None}
    if notion_type == "number":
        return {"number": float(value)}
    if notion_type == "select":
        return {"select": {"name": str(value)}}
    if notion_type == "date":
        return {"date": {"start": str(value)}}
    if notion_type == "checkbox":
        return {"checkbox": bool(value)}
    # Default to rich_text.
    return {"rich_text": [{"text": {"content": str(value)}}]}


@register("notion")
class NotionAction(BaseAction):
    async def run(self, ctx: ActionContext) -> str:
        database_id = self.config.get("database_id")
        token = self.config.get("token") or self.secrets.get("notion_token")
        if not database_id or not token:
            raise ActionError("notion action requires database_id and token")

        title_field = self.config.get("title_field", "")
        title_value = str(ctx.fields.get(title_field) or ctx.event.raw_content[:60])

        properties: dict[str, Any] = {
            self.config.get("title_property", "Name"): {
                "title": [{"text": {"content": title_value}}]
            }
        }
        for prop_name, spec in (self.config.get("properties") or {}).items():
            field_name = spec.get("field")
            properties[prop_name] = _prop_value(spec.get("type", "rich_text"),
                                                ctx.fields.get(field_name))

        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }
        body = {"parent": {"database_id": database_id}, "properties": properties}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.notion.com/v1/pages", json=body, headers=headers
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ActionError(f"Notion create failed: {exc}") from exc
        return f"created page in db {database_id[:8]}…"
