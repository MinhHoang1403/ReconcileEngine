"""Explicit source-to-canonical mapping contracts and conservative suggestions."""

from dataclasses import dataclass, field

from smartrecon.domain.statuses import Currency

ORDER_REQUIRED = {"order_id", "ordered_at", "expected_amount"}
BANK_REQUIRED = {
    "bank_txn_id",
    "txn_date",
    "posted_amount",
    "direction",
    "amount_basis",
}

ALIASES: dict[str, tuple[str, ...]] = {
    "order_id": ("order_id", "order_ref", "receivable_id", "invoice_id"),
    "ordered_at": ("ordered_at", "order_date", "tx_date", "created_at"),
    "expected_amount": ("expected_amount", "amount", "order_amount", "receivable"),
    "order_status": ("order_status", "status"),
    "bank_txn_id": ("bank_txn_id", "tx_id", "transaction_id", "bank_id"),
    "txn_ref": ("txn_ref", "bank_ref", "reference"),
    "txn_date": ("txn_date", "clear_date", "posting_date", "transaction_date"),
    "value_date": ("value_date", "effective_date"),
    "posted_amount": ("posted_amount", "net_amount", "credit_amount", "amount"),
    "direction": ("direction", "credit_debit", "transaction_type"),
    "amount_basis": ("amount_basis", "basis"),
    "description": ("description", "memo", "narrative"),
    "currency": ("currency", "currency_code"),
    "external_ref": ("external_ref", "payment_ref", "invoice_ref"),
    "customer_id": ("customer_id",),
    "customer_name": ("customer_name", "sender_name", "payer_name"),
    "payment_channel": ("payment_channel", "payment_method", "channel"),
    "sender_name": ("sender_name", "payer_name"),
    "channel": ("channel", "payment_channel"),
    "batch_ref": ("batch_ref", "settlement_ref"),
    "declared_fee": ("declared_fee", "fee", "fee_amount"),
}


@dataclass(frozen=True, slots=True)
class MappingConfig:
    """User-confirmed column and parsing semantics for both feeds."""

    order_columns: dict[str, str]
    bank_columns: dict[str, str]
    currency: Currency
    source_profile: str = "BANK_CREDIT"
    date_format: str = "%Y-%m-%d"
    decimal_separator: str = "."
    thousand_separator: str | None = ","
    order_defaults: dict[str, str] = field(default_factory=lambda: {"order_status": "ELIGIBLE"})
    bank_defaults: dict[str, str] = field(default_factory=dict)


def suggest_mapping(columns: list[str], canonical_fields: set[str]) -> dict[str, str]:
    """Suggest only exact normalized aliases; a user must still confirm them."""
    normalized = {column.strip().casefold(): column for column in columns}
    suggestions: dict[str, str] = {}
    for canonical in sorted(canonical_fields):
        for alias in ALIASES.get(canonical, (canonical,)):
            if alias.casefold() in normalized:
                suggestions[canonical] = normalized[alias.casefold()]
                break
    return suggestions


def default_demo_mapping() -> MappingConfig:
    """Return the explicit contract used by the generated demo files."""
    return MappingConfig(
        order_columns={
            "order_id": "order_id",
            "ordered_at": "ordered_at",
            "expected_amount": "expected_amount",
            "currency": "currency",
            "order_status": "order_status",
            "customer_name": "customer_name",
            "payment_channel": "payment_channel",
            "external_ref": "external_ref",
            "description": "description",
        },
        bank_columns={
            "bank_txn_id": "bank_txn_id",
            "txn_ref": "txn_ref",
            "txn_date": "txn_date",
            "value_date": "value_date",
            "direction": "direction",
            "posted_amount": "posted_amount",
            "currency": "currency",
            "amount_basis": "amount_basis",
            "description": "description",
            "sender_name": "sender_name",
            "channel": "channel",
            "batch_ref": "batch_ref",
            "declared_fee": "declared_fee",
        },
        currency=Currency.VND,
    )
