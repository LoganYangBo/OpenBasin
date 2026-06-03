import json

import pytest

from server.actions import build_action
from server.actions.base import ActionContext, render
from server.models import SignalEvent, SignalType


def _ctx(fields):
    event = SignalEvent(
        event_id="e", device_id="d", signal_type=SignalType.SMS,
        raw_content="raw", sender="Chase",
    )
    return ActionContext(event=event, fields=fields)


def test_render_interpolates_fields():
    ctx = _ctx({"merchant": "Cafe", "amount": 5.0, "currency": "$"})
    assert render("{merchant} {currency}{amount}", ctx) == "Cafe $5.0"


def test_render_leaves_unknown_placeholder():
    ctx = _ctx({})
    assert render("{nope}", ctx) == "{nope}"


@pytest.mark.asyncio
async def test_file_action_appends_jsonl(tmp_path):
    path = tmp_path / "out.jsonl"
    action = build_action({"type": "file", "path": str(path)})
    detail = await action.run(_ctx({"merchant": "Cafe", "amount": 5.0}))
    assert "appended" in detail
    line = json.loads(path.read_text().strip())
    assert line["merchant"] == "Cafe"
    assert line["signal_type"] == "sms"


def test_unknown_action_raises():
    from server.actions.base import ActionError

    with pytest.raises(ActionError):
        build_action({"type": "does-not-exist"})
