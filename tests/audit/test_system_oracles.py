"""Independent arithmetic oracles for the accepted synthetic demo.

These checks deliberately aggregate domain records directly instead of calling
the production KPI or conservation helpers under test.
"""

from collections import Counter, defaultdict
from pathlib import Path

from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.statuses import AmountBasis, Currency, Direction, LinkStatus, OrderStatus
from smartrecon.engine import run_reconciliation
from smartrecon.ingest.mapping import default_demo_mapping
from smartrecon.ingest.normalization import normalize_bundle
from smartrecon.ingest.readers import read_source_bundle

DEMO_DIR = Path("data/demo/vn_synthetic_demo")


def _demo_result():
    normalized = normalize_bundle(
        read_source_bundle(
            orders_path=DEMO_DIR / "internal_receivables.csv",
            bank_path=DEMO_DIR / "bank_transactions.csv",
        ),
        default_demo_mapping(),
    )
    return normalized, run_reconciliation(normalized, ReconciliationPolicy(currency=Currency.VND))


def test_demo_money_equations_hold_per_row_group_and_whole_run() -> None:
    normalized, result = _demo_result()
    cash_by_order: defaultdict[str, int] = defaultdict(int)
    cash_by_bank: defaultdict[str, int] = defaultdict(int)
    adjustments_by_order: defaultdict[str, int] = defaultdict(int)

    for edge in result.allocations:
        assert edge.allocated_cash_minor >= 0
        cash_by_order[edge.order_id] += edge.allocated_cash_minor
        cash_by_bank[edge.bank_txn_id] += edge.allocated_cash_minor
    for adjustment in result.adjustments:
        assert adjustment.amount_minor >= 0
        adjustments_by_order[adjustment.order_id] += adjustment.amount_minor

    eligible_orders = [order for order in result.orders if order.order_status is OrderStatus.ELIGIBLE]
    excluded_duplicates = set(normalized.duplicate_bank_ids)
    eligible_banks = [
        bank
        for bank in result.bank_transactions
        if bank.bank_txn_id not in excluded_duplicates
        and bank.direction is Direction.CREDIT
        and bank.amount_basis in {AmountBasis.POSTED_CASH, AmountBasis.NET_SETTLEMENT}
        and bank.currency is Currency.VND
    ]

    for order in eligible_orders:
        outstanding = order.expected_amount_minor - cash_by_order[order.order_id] - adjustments_by_order[order.order_id]
        assert outstanding >= 0
        assert order.expected_amount_minor == (
            cash_by_order[order.order_id] + adjustments_by_order[order.order_id] + outstanding
        )
        assert outstanding == result.order_outstanding_minor[order.order_id]
    for bank in eligible_banks:
        unapplied = bank.eligible_credit_minor - cash_by_bank[bank.bank_txn_id]
        assert unapplied >= 0
        assert bank.eligible_credit_minor == cash_by_bank[bank.bank_txn_id] + unapplied
        assert unapplied == result.bank_unapplied_minor[bank.bank_txn_id]

    group_ids = {group.group_id for group in result.groups if group.link_status is LinkStatus.CONFIRMED}
    assert all(edge.group_id in group_ids for edge in result.allocations)
    for group_id in group_ids:
        group = next(item for item in result.groups if item.group_id == group_id)
        group_edges = [edge for edge in result.allocations if edge.group_id == group_id]
        assert {edge.order_id for edge in group_edges} <= set(group.order_ids)
        assert {edge.bank_txn_id for edge in group_edges} <= set(group.bank_txn_ids)

    expected_total = sum(order.expected_amount_minor for order in eligible_orders)
    allocated_total = sum(edge.allocated_cash_minor for edge in result.allocations)
    adjustment_total = sum(item.amount_minor for item in result.adjustments)
    outstanding_total = sum(result.order_outstanding_minor[order.order_id] for order in eligible_orders)
    bank_total = sum(bank.eligible_credit_minor for bank in eligible_banks)
    unapplied_total = sum(result.bank_unapplied_minor[bank.bank_txn_id] for bank in eligible_banks)

    assert (expected_total, allocated_total, adjustment_total, outstanding_total) == (
        67_865_000,
        66_431_000,
        2_000,
        1_432_000,
    )
    assert expected_total == allocated_total + adjustment_total + outstanding_total
    assert bank_total == allocated_total + unapplied_total


def test_demo_fee_counts_and_statuses_are_derived_from_result_records() -> None:
    _, result = _demo_result()
    fee_adjustment = next(item for item in result.adjustments if item.order_id == "ORD00018")
    fee_edges = [item for item in result.allocations if item.order_id == "ORD00018"]

    assert fee_adjustment.amount_minor == 2_000
    assert fee_adjustment.adjustment_type == "PSP_FEE"
    assert fee_adjustment.evidence_reference == "declared_fee:TXN00016"
    assert sum(item.allocated_cash_minor for item in fee_edges) == 98_000
    assert {item.bank_txn_id for item in fee_edges} == {"TXN00016"}
    assert result.order_outstanding_minor["ORD00018"] == 0

    manual_layers = {layer: {"confirmed_groups": 0, "proposed_groups": 0} for layer in ("L1", "L2", "L3", "L4")}
    for group in result.groups:
        layer = group.evidence.rule_id.partition("_")[0]
        bucket = "confirmed_groups" if group.link_status is LinkStatus.CONFIRMED else "proposed_groups"
        manual_layers[layer][bucket] += 1
    assert manual_layers == result.layer_counts

    manual_statuses = Counter(status.value for status in result.payment_statuses.values())
    reported_statuses = {key: value for key, value in result.kpis["payment_status_counts"].items() if value}
    assert dict(manual_statuses) == reported_statuses
    assert sum(manual_statuses.values()) == result.kpis["eligible_orders_count"]
