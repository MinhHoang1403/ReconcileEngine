from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.models import BankTransaction, Order
from smartrecon.domain.statuses import (
    AmountBasis,
    Currency,
    Direction,
    GroupType,
    LinkStatus,
    PaymentStatus,
)
from smartrecon.engine import ReconciliationResult, run_reconciliation
from smartrecon.ingest.normalization import NormalizedBundle
from smartrecon.review import ReviewDecisionError, approve_group, reject_group

BASE_DATE = date(2026, 1, 1)


@dataclass(frozen=True, slots=True)
class GoldenFixture:
    fixture_id: str
    orders: tuple[Order, ...]
    banks: tuple[BankTransaction, ...]
    expected_edges: frozenset[tuple[str, str, int]] = frozenset()
    expected_payments: tuple[tuple[str, PaymentStatus], ...] = ()
    expected_adjustment: int = 0
    expected_exception: str | None = None
    expected_proposal_type: GroupType | None = None
    duplicate_bank_ids: tuple[str, ...] = ()


def order(
    order_id: str,
    amount: int,
    day: int = 0,
    *,
    currency: Currency = Currency.VND,
    external_ref: str | None = None,
    description: str | None = None,
    channel: str = "BANK_TRANSFER",
) -> Order:
    return Order(
        order_id,
        BASE_DATE + timedelta(days=day),
        amount,
        currency,
        external_ref=external_ref,
        description=description,
        payment_channel=channel,
    )


def bank(
    bank_id: str,
    amount: int,
    description: str,
    day: int = 0,
    *,
    currency: Currency = Currency.VND,
    direction: Direction = Direction.CREDIT,
    basis: AmountBasis = AmountBasis.POSTED_CASH,
    txn_ref: str | None = None,
    channel: str = "BANK",
    fee: int | None = None,
) -> BankTransaction:
    return BankTransaction(
        bank_id,
        BASE_DATE + timedelta(days=day),
        amount,
        direction,
        basis,
        currency,
        txn_ref=txn_ref or bank_id,
        description=description,
        channel=channel,
        declared_fee_minor=fee,
    )


GOLDEN_FIXTURES = (
    GoldenFixture(
        "F01",
        (order("O01", 300_000),),
        (bank("B01", 300_000, "Thanh toan O01"),),
        frozenset({("O01", "B01", 300_000)}),
        (("O01", PaymentStatus.FULL),),
    ),
    GoldenFixture(
        "F02",
        (order("O02", 200_000),),
        (bank("B02", 200_000, "Thanh toan O02", 2),),
        frozenset({("O02", "B02", 200_000)}),
        (("O02", PaymentStatus.FULL),),
    ),
    GoldenFixture(
        "F03",
        (order("O03", 100_000, external_ref="ORD-00003"),),
        (bank("B03", 100_000, "thanh toan ord 00003"),),
        frozenset({("O03", "B03", 100_000)}),
        (("O03", PaymentStatus.FULL),),
    ),
    GoldenFixture(
        "F04",
        (order("O04", 100_000, external_ref="ORD00004"),),
        (bank("B04", 100_000, "0RD00004"),),
        expected_payments=(("O04", PaymentStatus.UNKNOWN),),
        expected_exception="AMBIGUOUS_CANDIDATES",
        expected_proposal_type=GroupType.ONE_TO_ONE,
    ),
    GoldenFixture(
        "F05",
        (order("O05", 100_000), order("O06", 100_000)),
        (bank("B05", 100_000, ""),),
        expected_payments=(
            ("O05", PaymentStatus.UNKNOWN),
            ("O06", PaymentStatus.UNKNOWN),
        ),
        expected_exception="AMBIGUOUS_CANDIDATES",
        expected_proposal_type=GroupType.ONE_TO_ONE,
    ),
    GoldenFixture(
        "F06",
        (order("O07", 300_000), order("O08", 200_000)),
        (bank("B06", 500_000, "O07 O08"),),
        frozenset({("O07", "B06", 300_000), ("O08", "B06", 200_000)}),
        (("O07", PaymentStatus.FULL), ("O08", PaymentStatus.FULL)),
    ),
    GoldenFixture(
        "F07",
        (order("O09", 300_000), order("O10", 200_000)),
        (bank("B07", 500_000, "Tong hop"),),
        expected_payments=(
            ("O09", PaymentStatus.UNKNOWN),
            ("O10", PaymentStatus.UNKNOWN),
        ),
        expected_exception="AMBIGUOUS_CANDIDATES",
        expected_proposal_type=GroupType.MANY_ORDERS_ONE_BANK,
    ),
    GoldenFixture(
        "F08",
        (order("O11", 600_000),),
        (bank("B08", 200_000, "Dot 1 O11"), bank("B09", 400_000, "Dot 2 O11", 1)),
        frozenset({("O11", "B08", 200_000), ("O11", "B09", 400_000)}),
        (("O11", PaymentStatus.FULL),),
    ),
    GoldenFixture(
        "F09",
        (order("O12", 500_000),),
        (bank("B10", 490_000, "O12"),),
        frozenset({("O12", "B10", 490_000)}),
        (("O12", PaymentStatus.PARTIAL),),
        expected_exception="PARTIAL_PAYMENT",
    ),
    GoldenFixture(
        "F10",
        (order("O13", 500_000),),
        (bank("B11", 520_000, "O13"),),
        frozenset({("O13", "B11", 500_000)}),
        (("O13", PaymentStatus.OVERPAID),),
        expected_exception="OVERPAY_RESIDUAL",
    ),
    GoldenFixture(
        "F11",
        (order("O14", 150_000),),
        (),
        expected_payments=(("O14", PaymentStatus.NO_CONFIRMED_RECEIPT),),
        expected_exception="NO_CONFIRMED_RECEIPT",
    ),
    GoldenFixture(
        "F12",
        (),
        (bank("B12", 85_000, "Khong ro"),),
        expected_exception="ORPHAN_BANK",
    ),
    GoldenFixture(
        "F13",
        (order("O15", 120_000),),
        (
            bank("B13-A", 120_000, "O15", txn_ref="STABLE-B13"),
            bank("B13-B", 120_000, "O15", txn_ref="STABLE-B13"),
        ),
        frozenset({("O15", "B13-A", 120_000)}),
        (("O15", PaymentStatus.FULL),),
        expected_exception="POSSIBLE_REIMPORT",
        duplicate_bank_ids=("B13-B",),
    ),
    GoldenFixture(
        "F14",
        (order("O16", 120_000), order("O17", 120_000)),
        (bank("B14", 120_000, "O16"), bank("B15", 120_000, "O17")),
        frozenset({("O16", "B14", 120_000), ("O17", "B15", 120_000)}),
        (("O16", PaymentStatus.FULL), ("O17", PaymentStatus.FULL)),
    ),
    GoldenFixture(
        "F15",
        (order("O18", 100_000, channel="PSP"),),
        (
            bank(
                "B16",
                98_000,
                "O18 settlement",
                basis=AmountBasis.NET_SETTLEMENT,
                channel="PSP",
                fee=2_000,
            ),
        ),
        frozenset({("O18", "B16", 98_000)}),
        (("O18", PaymentStatus.FULL),),
        expected_adjustment=2_000,
    ),
    GoldenFixture(
        "F16",
        (order("O19", 100_000),),
        (bank("B17", 98_000, "O19"),),
        frozenset({("O19", "B17", 98_000)}),
        (("O19", PaymentStatus.PARTIAL),),
        expected_exception="PARTIAL_PAYMENT",
    ),
    GoldenFixture(
        "F17",
        (order("O20", 90_000),),
        (bank("B18", 90_000, "O20 refund", direction=Direction.DEBIT),),
        expected_payments=(("O20", PaymentStatus.NO_CONFIRMED_RECEIPT),),
        expected_exception="DEBIT_EXCLUDED",
    ),
    GoldenFixture(
        "F18",
        (order("DH01", 90_000), order("DH010", 80_000)),
        (bank("B19", 90_000, "Thanh toan DH01"),),
        frozenset({("DH01", "B19", 90_000)}),
        (
            ("DH01", PaymentStatus.FULL),
            ("DH010", PaymentStatus.NO_CONFIRMED_RECEIPT),
        ),
    ),
    GoldenFixture(
        "F21",
        (order("O26", 10_000, currency=Currency.BRL),),
        (bank("B21", 10_000, "O26", currency=Currency.VND),),
        expected_payments=(("O26", PaymentStatus.UNKNOWN),),
        expected_exception="CURRENCY_MISMATCH",
        expected_proposal_type=GroupType.ONE_TO_ONE,
    ),
    GoldenFixture(
        "F22",
        (order("00017", 17_000),),
        (bank("B22", 17_000, "Thanh toan 00017"),),
        frozenset({("00017", "B22", 17_000)}),
        (("00017", PaymentStatus.FULL),),
    ),
    GoldenFixture(
        "F23",
        (order("O28", 28_000, description='=HYPERLINK("https://invalid")'),),
        (bank("B23", 28_000, "O28"),),
        frozenset({("O28", "B23", 28_000)}),
        (("O28", PaymentStatus.FULL),),
    ),
    GoldenFixture(
        "F24",
        (order("O29", 130_000), order("O30", 170_000)),
        (bank("B24", 150_000, "O29 O30"), bank("B25", 150_000, "O29 O30", 1)),
        expected_payments=(
            ("O29", PaymentStatus.UNKNOWN),
            ("O30", PaymentStatus.UNKNOWN),
        ),
        expected_exception="COMPLEX_MANY_TO_MANY_REVIEW",
        expected_proposal_type=GroupType.AMBIGUOUS_CANDIDATES,
    ),
)

REVIEW_GOLDEN_FIXTURE_IDS = {"F19", "F20"}


def run_fixture(fixture: GoldenFixture) -> ReconciliationResult:
    normalized = NormalizedBundle(
        fixture.orders,
        fixture.banks,
        (),
        (),
        fixture.duplicate_bank_ids,
        {"orders": "fixture", "bank_transactions": "fixture"},
    )
    return run_reconciliation(normalized, ReconciliationPolicy(currency=Currency.VND))


@pytest.mark.parametrize("fixture", GOLDEN_FIXTURES, ids=lambda item: item.fixture_id)
def test_golden_oracle(fixture: GoldenFixture) -> None:
    result = run_fixture(fixture)
    actual_edges = frozenset(
        (edge.order_id, edge.bank_txn_id, edge.allocated_cash_minor) for edge in result.allocations
    )
    assert actual_edges == fixture.expected_edges
    assert result.conservation.is_valid
    assert result.kpis["confirmed_cash_allocated_minor"] == sum(edge[2] for edge in fixture.expected_edges)
    assert sum(item.amount_minor for item in result.adjustments) == fixture.expected_adjustment
    for order_id, expected_status in fixture.expected_payments:
        assert result.payment_statuses[order_id] is expected_status
    if fixture.expected_exception:
        assert any(fixture.expected_exception in exception.reason_codes for exception in result.exceptions)
    if fixture.expected_proposal_type:
        assert any(
            group.group_type is fixture.expected_proposal_type and group.link_status is LinkStatus.PROPOSED
            for group in result.groups
        )


def test_fixture_catalog_covers_all_24_business_cases() -> None:
    assert {fixture.fixture_id for fixture in GOLDEN_FIXTURES} == {
        *(f"F{number:02d}" for number in range(1, 19)),
        "F21",
        "F22",
        "F23",
        "F24",
    }
    assert {fixture.fixture_id for fixture in GOLDEN_FIXTURES} | REVIEW_GOLDEN_FIXTURE_IDS == {
        *(f"F{number:02d}" for number in range(1, 25)),
    }


def test_competing_approval_fixture_cannot_reuse_one_bank_credit() -> None:
    result = run_fixture(next(item for item in GOLDEN_FIXTURES if item.fixture_id == "F05"))
    proposals = [group for group in result.groups if group.link_status is LinkStatus.PROPOSED]
    first = approve_group(result, proposals[0].group_id)

    with pytest.raises(ReviewDecisionError) as error:
        approve_group(first, proposals[1].group_id)

    assert error.value.code == "ALLOCATION_CONFLICT"
    assert first.conservation.is_valid
    assert sum(edge.allocated_cash_minor for edge in first.allocations if edge.bank_txn_id == "B05") == 100_000


def test_undo_dependency_fixture_has_a_downstream_decision_to_preserve() -> None:
    result = run_fixture(next(item for item in GOLDEN_FIXTURES if item.fixture_id == "F05"))
    proposals = [group for group in result.groups if group.link_status is LinkStatus.PROPOSED]
    approved = approve_group(result, proposals[0].group_id)
    downstream = reject_group(approved, proposals[1].group_id)
    rejected = next(group for group in downstream.groups if group.group_id == proposals[1].group_id)
    original = next(group for group in result.groups if group.group_id == proposals[1].group_id)

    assert rejected.link_status is LinkStatus.REJECTED
    assert original.link_status is LinkStatus.PROPOSED
    assert downstream.conservation.is_valid
    # Restoring the snapshot before approval would erase the later rejection, so API undo must return 409.
    assert downstream != result


def test_ambiguous_proposals_never_enter_confirmed_cash_kpis() -> None:
    fixture = next(item for item in GOLDEN_FIXTURES if item.fixture_id == "F05")
    result = run_fixture(fixture)
    assert result.candidates
    assert not result.allocations
    assert result.kpis["confirmed_cash_allocated_minor"] == 0


def test_fuzzy_fixture_is_ranked_by_l3_without_auto_confirmation() -> None:
    fixture = next(item for item in GOLDEN_FIXTURES if item.fixture_id == "F04")
    result = run_fixture(fixture)
    assert any(candidate.evidence.rule_id == "L3_FUZZY_REFERENCE_CANDIDATE" for candidate in result.candidates)
    assert not result.allocations


def test_semantic_result_is_input_order_independent() -> None:
    fixture = next(item for item in GOLDEN_FIXTURES if item.fixture_id == "F14")
    forward = run_fixture(fixture)
    reversed_fixture = GoldenFixture(
        fixture.fixture_id,
        tuple(reversed(fixture.orders)),
        tuple(reversed(fixture.banks)),
        fixture.expected_edges,
        fixture.expected_payments,
    )
    backward = run_fixture(reversed_fixture)
    assert forward.semantic_checksum == backward.semantic_checksum
