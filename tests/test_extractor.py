import pytest

from server.extract.extractor import Extractor, _coerce, _extract_json
from server.models import SignalEvent, SignalType


def test_coerce_currency_string_to_float():
    assert _coerce("$128.50", "float") == 128.5
    assert _coerce("1,234.00", "float") == 1234.0


def test_coerce_bool_and_int():
    assert _coerce("yes", "bool") is True
    assert _coerce("0", "bool") is False
    assert _coerce("42", "int") == 42


def test_coerce_unparseable_is_none():
    assert _coerce("not a number", "float") is None


def test_extract_json_from_fenced_block():
    text = "Here you go:\n```json\n{\"merchant\": \"Cafe\", \"amount\": 5}\n```"
    assert _extract_json(text) == {"merchant": "Cafe", "amount": 5}


def test_extract_json_bare_object():
    assert _extract_json('prefix {"a": 1} suffix') == {"a": 1}


class _FakeLLM:
    def __init__(self, response):
        self._response = response

    async def complete(self, system, user):
        return self._response


@pytest.mark.asyncio
async def test_extractor_end_to_end_coerces_types():
    event = SignalEvent(
        event_id="e", device_id="d", signal_type=SignalType.SMS,
        raw_content="Chase charged $128.50 at Whole Foods", sender="Chase",
    )
    llm = _FakeLLM('{"merchant": "Whole Foods", "amount": "$128.50", "category": "Groceries"}')
    extractor = Extractor(llm)
    fields = await extractor.extract(
        event, {"merchant": "str", "amount": "float", "category": "str"}
    )
    assert fields == {"merchant": "Whole Foods", "amount": 128.5, "category": "Groceries"}
