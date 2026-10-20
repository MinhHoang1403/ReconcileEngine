from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.invariants import check_conservation
from smartrecon.domain.models import (
    AllocationEdge,
    BankTransaction,
    Order,
    VerifiedAdjustment,
)
from smartrecon.domain.statuses import AmountBasis, Currency, Direction
from smartrecon.engine import run_reconciliation
from smartrecon.ingest.normalization import NormalizedBundle


@given(
    expected=st.integers(min_value=0, max_value=10**12),
    posted=st.integers(min_value=0, max_value=10**12),
)
def test_single_edge_preserves_both_cash_and_receivable(expected: int, posted: int) -> None:
    allocated = min(expected, posted)
    order = Order("O", date(2026, 1, 1), expected, Currency.VND)
    bank = BankTransaction(
        "B",
        date(2026, 1, 1),
        posted,
        Direction.CREDIT,
        AmountBasis.POSTED_CASH,
        Currency.VND,
    )
    edges = [AllocationEdge("E", "G", "O", "B", allocated, Currency.VND)]

    report = check_conservation([order], [bank], edges)

    assert report.is_valid
    assert report.bank_unapplied["B"] == posted - allocated
    assert report.order_outstanding["O"] == expected - allocated
    assert posted == allocated + report.bank_unapplied["B"]
    assert expected == allocated + report.order_outstanding["O"]


def test_overallocation_is_detected_independently() -> None:
    order = Order("O", date(2026, 1, 1), 100, Currency.VND)
    bank = BankTransaction(
        "B",
        date(2026, 1, 1),
        90,
        Direction.CREDIT,
        AmountBasis.POSTED_CASH,
        Currency.VND,
    )
    edges = [AllocationEdge("E", "G", "O", "B", 110, Currency.VND)]

    report = check_conservation([order], [bank], edges)

    assert "BANK_OVERALLOCATED:B" in report.violations
    assert "ORDER_OVERFULFILLED:O" in report.violations


def test_many_orders_share_bank_cash_without_counting_bank_twice() -> None:
    orders = [
        Order("O1", date(2026, 1, 1), 300, Currency.VND),
        Order("O2", date(2026, 1, 1), 200, Currency.VND),
    ]
    bank = BankTransaction(
        "B",
        date(2026, 1, 1),
        500,
        Direction.CREDIT,
        AmountBasis.POSTED_CASH,
        Currency.VND,
    )
    edges = [
        AllocationEdge("E1", "G", "O1", "B", 300, Currency.VND),
        AllocationEdge("E2", "G", "O2", "B", 200, Currency.VND),
    ]

    report = check_conservation(orders, [bank], edges)

    assert report.is_valid
    assert report.bank_allocated == {"B": 500}
    assert report.bank_unapplied == {"B": 0}


def test_verified_fee_is_not_counted_as_bank_cash() -> None:
    order = Order("O", date(2026, 1, 1), 10_000, Currency.BRL)
    bank = BankTransaction(
        "B",
        date(2026, 1, 1),
        9_800,
        Direction.CREDIT,
        AmountBasis.NET_SETTLEMENT,
        Currency.BRL,
    )
    edge = AllocationEdge("E", "G", "O", "B", 9_800, Currency.BRL)
    fee = VerifiedAdjustment("F", "O", 200, "PSP_FEE", "fee-policy:test")

    report = check_conservation([order], [bank], [edge], [fee])

    assert report.is_valid
    assert report.bank_allocated["B"] == 9_800
    assert report.order_adjusted["O"] == 200
    assert report.order_outstanding["O"] == 0


@given(
    amounts=st.lists(st.integers(min_value=0, max_value=10**12), min_size=1, max_size=6),
    posted=st.integers(min_value=0, max_value=10**13),
)
def test_engine_group_cash_matches_independent_capacity_oracle(amounts: list[int], posted: int) -> None:
    orders = tuple(Order(f"O-{index}", date(2026, 1, 1), amount, Currency.VND) for index, amount in enumerate(amounts))
    banks = (
        BankTransaction(
            "BANK",
            date(2026, 1, 1),
            posted,
            Direction.CREDIT,
            AmountBasis.POSTED_CASH,
            Currency.VND,
            description=" ".join(order.order_id for order in orders),
        ),
    )
    inputs = NormalizedBundle(orders, banks, (), (), (), {})
    result = run_reconciliation(inputs, ReconciliationPolicy(Currency.VND))
    assert sum(edge.allocated_cash_minor for edge in result.allocations) == min(sum(amounts), posted)
    assert result.bank_unapplied_minor["BANK"] == max(0, posted - sum(amounts))
    assert sum(result.order_outstanding_minor.values()) == max(0, sum(amounts) - posted)
    assert result.conservation.is_valid
    for order in orders:
        assert sum(edge.allocated_cash_minor for edge in result.allocations if edge.order_id == order.order_id) <= (
            order.expected_amount_minor
        )
    reversed_result = run_reconciliation(
        NormalizedBundle(orders[::-1], banks, (), (), (), {}), ReconciliationPolicy(Currency.VND)
    )
    assert result.semantic_checksum == reversed_result.semantic_checksum
