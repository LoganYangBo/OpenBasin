from server.models import SignalEvent, SignalType
from server.pipeline.models import Pipeline


def _event(content="Your bank card was charged $10", signal_type=SignalType.SMS, app=None):
    return SignalEvent(
        event_id="e",
        device_id="d",
        signal_type=signal_type,
        source_app=app,
        raw_content=content,
        sender="+1",
    )


def _pipeline(**trigger):
    return Pipeline.model_validate({"name": "p", "trigger": trigger})


def test_signal_type_match():
    p = _pipeline(signal_type="sms")
    assert p.trigger.matches(_event()) is True
    assert p.trigger.matches(_event(signal_type=SignalType.EMAIL)) is False


def test_keyword_filter_or():
    p = _pipeline(signal_type="sms", filter="bank OR payment")
    assert p.trigger.matches(_event("bank charged")) is True
    assert p.trigger.matches(_event("a payment received")) is True
    assert p.trigger.matches(_event("hello friend")) is False


def test_keyword_filter_and():
    p = _pipeline(signal_type="sms", filter="amazon AND refund")
    assert p.trigger.matches(_event("amazon refund issued")) is True
    assert p.trigger.matches(_event("amazon order shipped")) is False


def test_source_app_filter():
    p = _pipeline(signal_type="notification", source_app="com.news")
    assert p.trigger.matches(_event(signal_type=SignalType.NOTIFICATION, app="com.news")) is True
    assert p.trigger.matches(_event(signal_type=SignalType.NOTIFICATION, app="com.other")) is False
