"""Pure analytics derived from one immutable reconciliation result."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from statistics import median
from typing import Any

from smartrecon.domain.statuses import LinkStatus
from smartrecon.engine import ReconciliationResult

_REVIEW_STATUSES = ("OPEN", "APPROVED", "REJECTED", "NEEDS_MORE_INFO", "UNDONE")
_GROUP_TYPES = ("ONE_TO_ONE", "MANY_ORDERS_ONE_BANK", "ONE_ORDER_MANY_BANKS", "MANY_TO_MANY")


def snapshot_analytics(result: ReconciliationResult) -> dict[str, Any]:
    """Summarize the effective snapshot without counting proposals as cash.

    The confirmation-rate denominator is every relation group in the snapshot
    (confirmed plus proposed). Lag observations are confirmed allocation pairs,
    because each pair has one unambiguous order date and bank transaction date.
    """

    confirmed_groups = [group for group in result.groups if group.link_status is LinkStatus.CONFIRMED]
    confirmed_count = len(confirmed_groups)
    group_count = len(result.groups)
    review_status_counts = Counter(group.review_status.value for group in result.groups)
    group_type_counts = Counter(group.group_type.value for group in confirmed_groups)
    reason_counts = Counter(code for item in result.exceptions for code in item.reason_codes)

    orders = {order.order_id: order for order in result.orders}
    banks = {bank.bank_txn_id: bank for bank in result.bank_transactions}
    lag_days = [
        (banks[edge.bank_txn_id].txn_date - orders[edge.order_id].ordered_at).days
        for edge in result.allocations
        if edge.order_id in orders and edge.bank_txn_id in banks
    ]

    expected = int(result.kpis.get("expected_receivable_minor", 0))
    return {
        "review_status_counts": {status: review_status_counts.get(status, 0) for status in _REVIEW_STATUSES},
        "method_summary": {
            "confirmed_groups": confirmed_count,
            "proposed_groups": group_count - confirmed_count,
            "total_relation_groups": group_count,
            "confirmation_rate_percent": round(confirmed_count * 100 / group_count, 2) if group_count else 0.0,
            "confirmation_rate_denominator": "ALL_RELATION_GROUPS",
        },
        "confirmed_group_type_counts": {kind: group_type_counts.get(kind, 0) for kind in _GROUP_TYPES},
        "exception_reason_counts": dict(sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))),
        "residual_distribution": {
            "denominator_minor": expected,
            "order_outstanding": _residual_buckets(result.order_outstanding_minor.values(), expected),
            "bank_unapplied": _residual_buckets(result.bank_unapplied_minor.values(), expected),
        },
        "confirmed_lag": {
            "observation_unit": "ALLOCATION_PAIR",
            "observations": len(lag_days),
            "median_days": float(median(lag_days)) if lag_days else None,
            "buckets": _lag_buckets(lag_days),
        },
    }


def _residual_buckets(values: Iterable[int], denominator: int) -> list[dict[str, int | str]]:
    buckets = {
        "UP_TO_1_PERCENT": {"count": 0, "amount_minor": 0},
        "ONE_TO_FIVE_PERCENT": {"count": 0, "amount_minor": 0},
        "OVER_FIVE_PERCENT": {"count": 0, "amount_minor": 0},
    }
    for raw_value in values:
        value = int(raw_value)
        if value <= 0:
            continue
        ratio = value / denominator if denominator > 0 else 1.0
        key = "UP_TO_1_PERCENT" if ratio <= 0.01 else "ONE_TO_FIVE_PERCENT" if ratio <= 0.05 else "OVER_FIVE_PERCENT"
        buckets[key]["count"] += 1
        buckets[key]["amount_minor"] += value
    return [{"bucket": key, **metrics} for key, metrics in buckets.items()]


def _lag_buckets(values: list[int]) -> list[dict[str, int | str]]:
    counts = Counter(
        "BEFORE_ORDER"
        if value < 0
        else "SAME_DAY"
        if value == 0
        else "ONE_DAY"
        if value == 1
        else "TWO_TO_THREE_DAYS"
        if value <= 3
        else "OVER_THREE_DAYS"
        for value in values
    )
    return [
        {"bucket": key, "count": counts.get(key, 0)}
        for key in ("BEFORE_ORDER", "SAME_DAY", "ONE_DAY", "TWO_TO_THREE_DAYS", "OVER_THREE_DAYS")
    ]
