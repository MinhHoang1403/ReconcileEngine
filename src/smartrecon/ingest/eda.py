"""Raw and standardized exploratory summaries with explicit confidence."""

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from smartrecon.domain.models import BankTransaction, Order
from smartrecon.domain.statuses import OrderStatus
from smartrecon.ingest.readers import RawTable


@dataclass(frozen=True, slots=True)
class RawEda:
    row_count: int
    column_count: int
    columns: tuple[str, ...]
    missing_by_column: dict[str, int]
    duplicate_rows: int
    sample_rows: tuple[dict[str, Any], ...]
    confidence: str = "PRELIMINARY_BEFORE_MAPPING"


@dataclass(frozen=True, slots=True)
class StandardizedEda:
    orders_count: int
    bank_rows_count: int
    eligible_orders_count: int
    eligible_credit_count: int
    expected_receivable_minor: int
    eligible_bank_credit_minor: int
    order_date_min: date | None
    order_date_max: date | None
    bank_date_min: date | None
    bank_date_max: date | None
    currency: str


def summarize_raw(table: RawTable, sample_size: int = 20) -> RawEda:
    frame = table.frame
    missing = {str(column): int(frame[column].astype("string").str.strip().eq("").sum()) for column in frame.columns}
    sample = tuple(frame.head(sample_size).astype(object).to_dict(orient="records"))
    return RawEda(
        row_count=len(frame),
        column_count=len(frame.columns),
        columns=tuple(str(column) for column in frame.columns),
        missing_by_column=missing,
        duplicate_rows=int(frame.duplicated().sum()),
        sample_rows=sample,
    )


def summarize_standardized(
    orders: list[Order], bank_transactions: list[BankTransaction], currency: str
) -> StandardizedEda:
    eligible_orders = [row for row in orders if row.order_status is OrderStatus.ELIGIBLE]
    eligible_bank = [row for row in bank_transactions if row.eligible_credit_minor > 0]
    order_dates = [row.ordered_at for row in orders]
    bank_dates = [row.txn_date for row in bank_transactions]
    return StandardizedEda(
        orders_count=len(orders),
        bank_rows_count=len(bank_transactions),
        eligible_orders_count=len(eligible_orders),
        eligible_credit_count=len(eligible_bank),
        expected_receivable_minor=sum(row.expected_amount_minor for row in eligible_orders),
        eligible_bank_credit_minor=sum(row.eligible_credit_minor for row in eligible_bank),
        order_date_min=min(order_dates, default=None),
        order_date_max=max(order_dates, default=None),
        bank_date_min=min(bank_dates, default=None),
        bank_date_max=max(bank_dates, default=None),
        currency=currency,
    )


def eda_to_dict(summary: RawEda | StandardizedEda) -> dict[str, Any]:
    """Convert dataclass summaries to JSON-ready primitive values."""
    result = asdict(summary)
    for key, value in result.items():
        if isinstance(value, date):
            result[key] = value.isoformat()
    return result
