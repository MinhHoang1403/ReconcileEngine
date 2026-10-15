"""Safe conversion between source money strings and integer minor units."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from smartrecon.domain.statuses import Currency

MINOR_DIGITS: dict[Currency, int] = {Currency.VND: 0, Currency.BRL: 2}


class MoneyParseError(ValueError):
    """Raised when source money cannot be interpreted without ambiguity."""


def parse_minor_units(
    value: str | int | Decimal,
    currency: Currency,
    *,
    decimal_separator: str = ".",
    thousand_separator: str | None = ",",
) -> int:
    """Parse a non-negative source amount with explicit separator semantics."""
    if decimal_separator not in {".", ","}:
        raise MoneyParseError("Dấu thập phân chỉ hỗ trợ '.' hoặc ','")
    if thousand_separator == decimal_separator:
        raise MoneyParseError("Dấu hàng nghìn và thập phân phải khác nhau")

    raw = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not raw:
        raise MoneyParseError("Số tiền rỗng")
    if thousand_separator:
        raw = raw.replace(thousand_separator, "")
    if decimal_separator != ".":
        raw = raw.replace(decimal_separator, ".")

    try:
        amount = Decimal(raw)
    except InvalidOperation as exc:
        raise MoneyParseError(f"Không thể parse số tiền: {value!r}") from exc
    if not amount.is_finite() or amount < 0:
        raise MoneyParseError("Số tiền phải hữu hạn và không âm")

    if currency is Currency.VND:
        if amount != amount.to_integral_value():
            raise MoneyParseError(f"Số tiền VND phải có phần thập phân bằng 0, nhận được: {value!r}")
        return int(amount)

    digits = MINOR_DIGITS[currency]
    factor = Decimal(10) ** digits
    quantized = amount.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return int(quantized * factor)


def format_minor_units(amount_minor: int, currency: Currency) -> str:
    """Format minor units deterministically without float conversion."""
    digits = MINOR_DIGITS[currency]
    amount = Decimal(amount_minor) / (Decimal(10) ** digits)
    return f"{amount:.{digits}f} {currency.value}"
