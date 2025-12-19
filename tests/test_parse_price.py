from src.utils import parse_price


def test_parse_price_simple():
    assert parse_price("$12,345") == 12345.0


def test_parse_price_decimal():
    assert parse_price("$12,345.67") == 12345.67


def test_parse_price_eu_style():
    assert parse_price("12.345,67") == 12345.67
