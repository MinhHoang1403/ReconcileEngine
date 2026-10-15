"""Deterministic KPI calculations with separate order, bank-row, and money denominators."""

from collections import defaultdict
from typing import Any

from smartrecon.domain.models import (
    AllocationEdge,
    BankTransaction,
    ExceptionCase,
    MatchGroup,
    Order,
    VerifiedAdjustment,
)
from smartrecon.domain.statuses import GroupType, LinkStatus, OrderStatus, PaymentStatus


def calculate_kpis(
    orders: list[Order],
    eligible_banks: list[BankTransaction],
    groups: list[MatchGroup],
    allocations: list[AllocationEdge],
    adjustments: list[VerifiedAdjustment],
    exceptions: list[ExceptionCase],
) -> dict[str, Any]:
    """Calculate snapshot KPIs without counting proposed allocations or repeated bank values."""
    eligible_orders = [order for order in orders if order.order_status is OrderStatus.ELIGIBLE]
    cash_by_order: defaultdict[str, int] = defaultdict(int)
    cash_by_bank: defaultdict[str, int] = defaultdict(int)
    adjustment_by_order: defaultdict[str, int] = defaultdict(int)
    for edge in allocations:
        cash_by_order[edge.order_id] += edge.allocated_cash_minor
        cash_by_bank[edge.bank_txn_id] += edge.allocated_cash_minor
    for adjustment in adjustments:
        adjustment_by_order[adjustment.order_id] += adjustment.amount_minor

    outstanding = {
        order.order_id: order.expected_amount_minor
        - cash_by_order[order.order_id]
        - adjustment_by_order[order.order_id]
        for order in eligible_orders
    }
    unapplied = {
        bank.bank_txn_id: bank.eligible_credit_minor - cash_by_bank[bank.bank_txn_id] for bank in eligible_banks
    }
    confirmed_payment_statuses = {
        order_id: status
        for group in groups
        for order_id, status in group.payment_statuses.items()
        if group.link_status is LinkStatus.CONFIRMED
    }
    proposed_orders = {
        order_id for group in groups if group.link_status is LinkStatus.PROPOSED for order_id in group.order_ids
    }
    payment_statuses: dict[str, PaymentStatus] = {}
    for order in eligible_orders:
        fulfilled = cash_by_order[order.order_id] + adjustment_by_order[order.order_id]
        if order.order_id in confirmed_payment_statuses:
            payment_statuses[order.order_id] = confirmed_payment_statuses[order.order_id]
        elif fulfilled > 0 and outstanding[order.order_id] > 0:
            payment_statuses[order.order_id] = PaymentStatus.PARTIAL
        elif fulfilled == 0 and order.order_id in proposed_orders:
            payment_statuses[order.order_id] = PaymentStatus.UNKNOWN
        else:
            payment_statuses[order.order_id] = PaymentStatus.NO_CONFIRMED_RECEIPT
    return {
        "currency": eligible_orders[0].currency.value if eligible_orders else None,
        "eligible_orders_count": len(eligible_orders),
        "bank_eligible_credit_count": len(eligible_banks),
        "confirmed_link_orders_count": sum(cash_by_order[order.order_id] > 0 for order in eligible_orders),
        "fully_settled_orders_count": sum(
            payment_statuses[order.order_id] in {PaymentStatus.FULL, PaymentStatus.OVERPAID}
            for order in eligible_orders
        ),
        "partially_settled_orders_count": sum(
            cash_by_order[order.order_id] + adjustment_by_order[order.order_id] > 0 and outstanding[order.order_id] > 0
            for order in eligible_orders
        ),
        "no_confirmed_receipt_orders_count": sum(cash_by_order[order.order_id] == 0 for order in eligible_orders),
        "confirmed_bank_rows_count": sum(cash_by_bank[bank.bank_txn_id] > 0 for bank in eligible_banks),
        "unallocated_bank_rows_count": sum(value > 0 for value in unapplied.values()),
        "expected_receivable_minor": sum(order.expected_amount_minor for order in eligible_orders),
        "confirmed_cash_allocated_minor": sum(edge.allocated_cash_minor for edge in allocations),
        "verified_adjustments_minor": sum(item.amount_minor for item in adjustments),
        "outstanding_receivable_minor": sum(outstanding.values()),
        "unapplied_bank_credit_minor": sum(unapplied.values()),
        "grouped_n1_count": sum(
            group.link_status is LinkStatus.CONFIRMED and group.group_type is GroupType.MANY_ORDERS_ONE_BANK
            for group in groups
        ),
        "split_1n_count": sum(
            group.link_status is LinkStatus.CONFIRMED and group.group_type is GroupType.ONE_ORDER_MANY_BANKS
            for group in groups
        ),
        "proposed_groups_count": sum(group.link_status is LinkStatus.PROPOSED for group in groups),
        "unresolved_exceptions_count": len(exceptions),
        "payment_status_counts": {
            status.value: sum(value is status for value in payment_statuses.values()) for status in PaymentStatus
        },
    }
