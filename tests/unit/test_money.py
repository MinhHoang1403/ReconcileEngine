from decimal import Decimal

import pytest

from smartrecon.domain.money import MoneyParseError, format_minor_units, parse_minor_units
from smartrecon.domain.statuses import Currency


@pytest.mark.parametrize(
    ("raw", "currency", "decimal_separator", "thousand_separator", "expected"),
    [
        ("300,000", Currency.VND, ".", ",", 300_000),
        ("123,45", Currency.BRL, ",", ".", 12_345),
        (Decimal("10.005"), Currency.BRL, ".", ",", 1_001),
        ("00017", Currency.VND, ".", ",", 17),
    ],
)
def test_parse_minor_units(
    raw: str | Decimal,
    currency: Currency,
    decimal_separator: str,
    thousand_separator: str,
    expected: int,
) -> None:
    assert (
        parse_minor_units(
            raw,
            currency,
            decimal_separator=decimal_separator,
            thousand_separator=thousand_separator,
        )
        == expected
    )


def test_invalid_and_negative_money_is_rejected() -> None:
    with pytest.raises(MoneyParseError):
        parse_minor_units("-1", Currency.VND)
    with pytest.raises(MoneyParseError):
        parse_minor_units("NaN", Currency.BRL)


@pytest.mark.parametrize(
    ("raw", "decimal_separator", "thousand_separator", "expected"),
    [
        ("100000.0", ".", ",", 100_000),
        ("100.000,000", ",", ".", 100_000),
        (Decimal("1E+3"), ".", ",", 1_000),
    ],
)
def test_vnd_accepts_only_numerically_integral_values(
    raw: str | Decimal,
    decimal_separator: str,
    thousand_separator: str,
    expected: int,
) -> None:
    assert (
        parse_minor_units(
            raw,
            Currency.VND,
            decimal_separator=decimal_separator,
            thousand_separator=thousand_separator,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("raw", "decimal_separator", "thousand_separator"),
    [
        ("100000.5", ".", ","),
        ("100.000,5", ",", "."),
        (Decimal("0.1"), ".", ","),
    ],
)
def test_vnd_rejects_nonzero_fraction_without_rounding(
    raw: str | Decimal,
    decimal_separator: str,
    thousand_separator: str,
) -> None:
    with pytest.raises(MoneyParseError, match="VND") as error:
        parse_minor_units(
            raw,
            Currency.VND,
            decimal_separator=decimal_separator,
            thousand_separator=thousand_separator,
        )

    assert str(raw) in str(error.value)


def test_brl_round_half_up_policy_is_unchanged() -> None:
    assert parse_minor_units("1.005", Currency.BRL) == 101


def test_format_minor_units_does_not_use_float() -> None:
    assert format_minor_units(12_345, Currency.BRL) == "123.45 BRL"
    assert format_minor_units(300_000, Currency.VND) == "300000 VND"
