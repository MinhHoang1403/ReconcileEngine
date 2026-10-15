"""Independent conservation checks over effective confirmed allocations."""

from collections import defaultdict
from dataclasses import dataclass

from smartrecon.domain.models import (
    AllocationEdge,
    BankTransaction,
    Order,
    VerifiedAdjustment,
)
from smartrecon.domain.statuses import OrderStatus


@dataclass(frozen=True, slots=True)
class ConservationReport:
    bank_allocated: dict[str, int]
    bank_unapplied: dict[str, int]
    order_allocated: dict[str, int]
    order_adjusted: dict[str, int]
    order_outstanding: dict[str, int]
    violations: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.violations


def check_conservation(
    orders: list[Order],
    bank_transactions: list[BankTransaction],
    allocations: list[AllocationEdge],
    adjustments: list[VerifiedAdjustment] | None = None,
) -> ConservationReport:
    """Validate row-level and whole-run cash/receivable conservation identities."""
    adjustments = adjustments or []
    order_by_id = {order.order_id: order for order in orders}
    bank_by_id = {bank.bank_txn_id: bank for bank in bank_transactions}
    violations: list[str] = []

    if len(order_by_id) != len(orders):
        violations.append("DUPLICATE_ORDER_ID")
    if len(bank_by_id) != len(bank_transactions):
        violations.append("DUPLICATE_BANK_TXN_ID")

    bank_allocated: defaultdict[str, int] = defaultdict(int)
    order_allocated: defaultdict[str, int] = defaultdict(int)
    order_adjusted: defaultdict[str, int] = defaultdict(int)

    for edge in allocations:
        order = order_by_id.get(edge.order_id)
        bank = bank_by_id.get(edge.bank_txn_id)
        if order is None:
            violations.append(f"UNKNOWN_ORDER:{edge.edge_id}")
            continue
        if bank is None:
            violations.append(f"UNKNOWN_BANK:{edge.edge_id}")
            continue
        if order.currency != edge.currency or bank.currency != edge.currency:
            violations.append(f"CURRENCY_MISMATCH:{edge.edge_id}")
            continue
        bank_allocated[bank.bank_txn_id] += edge.allocated_cash_minor
        order_allocated[order.order_id] += edge.allocated_cash_minor

    for adjustment in adjustments:
        if adjustment.order_id not in order_by_id:
            violations.append(f"UNKNOWN_ADJUSTMENT_ORDER:{adjustment.adjustment_id}")
            continue
        order_adjusted[adjustment.order_id] += adjustment.amount_minor

    bank_unapplied: dict[str, int] = {}
    for bank in bank_transactions:
        eligible = bank.eligible_credit_minor
        allocated = bank_allocated[bank.bank_txn_id]
        unapplied = eligible - allocated
        bank_unapplied[bank.bank_txn_id] = unapplied
        if allocated < 0 or allocated > eligible:
            violations.append(f"BANK_OVERALLOCATED:{bank.bank_txn_id}")

    order_outstanding: dict[str, int] = {}
    for order in orders:
        eligible = order.order_status is OrderStatus.ELIGIBLE
        expected = order.expected_amount_minor if eligible else 0
        fulfilled = order_allocated[order.order_id] + order_adjusted[order.order_id]
        outstanding = expected - fulfilled
        order_outstanding[order.order_id] = outstanding
        if fulfilled < 0 or fulfilled > expected:
            violations.append(f"ORDER_OVERFULFILLED:{order.order_id}")

    total_bank = sum(bank.eligible_credit_minor for bank in bank_transactions)
    total_allocated = sum(edge.allocated_cash_minor for edge in allocations)
    if total_bank != total_allocated + sum(bank_unapplied.values()):
        violations.append("RUN_BANK_CONSERVATION")

    total_orders = sum(
        order.expected_amount_minor
        for order in orders
        if order.order_status is OrderStatus.ELIGIBLE
    )
    if total_orders != (
        total_allocated + sum(order_adjusted.values()) + sum(order_outstanding.values())
    ):
        violations.append("RUN_ORDER_CONSERVATION")

    return ConservationReport(
        bank_allocated=dict(bank_allocated),
        bank_unapplied=bank_unapplied,
        order_allocated=dict(order_allocated),
        order_adjusted=dict(order_adjusted),
        order_outstanding=order_outstanding,
        violations=tuple(sorted(set(violations))),
    )
