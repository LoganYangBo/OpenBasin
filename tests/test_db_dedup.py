from server.db import EventStore
from server.models import SignalEvent, SignalType


def _event(**kw) -> SignalEvent:
    base = dict(
        event_id="e1",
        device_id="pixel-8",
        signal_type=SignalType.SMS,
        raw_content="Charged $5 at Cafe",
        sender="+100",
    )
    base.update(kw)
    return SignalEvent(**base)


def test_insert_then_duplicate_event_id():
    store = EventStore(":memory:")
    assert store.insert(_event()) is True
    # Same event_id → rejected.
    assert store.insert(_event()) is False
    assert store.count() == 1


def test_duplicate_by_content_hash_different_id():
    store = EventStore(":memory:")
    assert store.insert(_event(event_id="a")) is True
    # Different id but identical content → content_hash collision → rejected.
    assert store.insert(_event(event_id="b")) is False
    assert store.count() == 1


def test_distinct_content_inserts():
    store = EventStore(":memory:")
    assert store.insert(_event(event_id="a", raw_content="one")) is True
    assert store.insert(_event(event_id="b", raw_content="two")) is True
    assert store.count() == 2


def test_content_hash_is_derived():
    e = _event()
    assert e.content_hash and len(e.content_hash) == 64
