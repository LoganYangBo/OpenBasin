import pytest

from server.pipeline.conditions import ConditionError, all_pass, evaluate


def test_numeric_comparison():
    assert evaluate("amount > 100", {"amount": 128.5}) is True
    assert evaluate("amount > 100", {"amount": 50}) is False


def test_string_inequality():
    assert evaluate("merchant != 'Internal Transfer'", {"merchant": "Whole Foods"}) is True
    assert evaluate("merchant != 'Internal Transfer'", {"merchant": "Internal Transfer"}) is False


def test_boolean_and_membership():
    names = {"amount": 200, "category": "Dining"}
    assert evaluate("amount >= 100 and category in ['Dining', 'Travel']", names) is True


def test_unknown_field_is_none():
    # Missing field degrades to None rather than raising.
    assert evaluate("amount > 100", {}) is False


def test_all_pass():
    names = {"amount": 200, "merchant": "Shop"}
    assert all_pass(["amount > 100", "merchant != 'X'"], names) is True
    assert all_pass(["amount > 100", "amount < 150"], names) is False


def test_disallows_calls():
    with pytest.raises(ConditionError):
        evaluate("__import__('os').system('echo hi')", {})
