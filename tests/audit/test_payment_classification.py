"""Business oracles distinguish bank residual ownership from order fulfillment."""

from datetime import date

import pytest

from research.classification_evaluation import cases, run_case
from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.models import BankTransaction, Order
from smartrecon.domain.statuses import AmountBasis, Currency, Direction, PaymentStatus
from smartrecon.engine import run_reconciliation
from smartrecon.ingest.normalization import NormalizedBundle


def test_shared_overpayment_is_not_attributed_to_every_order() -> None:
    orders = (
        Order("ORDER-A", date(2026, 10, 20), 100000, Currency.VND),
        Order("ORDER-B", date(2026, 10, 20), 200000, Currency.VND),
    )
    banks = (
        BankTransaction(
            "BANK-1",
            date(2026, 10, 20),
            350000,
            Direction.CREDIT,
            AmountBasis.POSTED_CASH,
            Currency.VND,
            description="ORDER-A ORDER-B",
        ),
    )
    result = run_reconciliation(NormalizedBundle(orders, banks, (), (), (), {}), ReconciliationPolicy(Currency.VND))
    assert {(edge.order_id, edge.allocated_cash_minor) for edge in result.allocations} == {
        ("ORDER-A", 100000),
        ("ORDER-B", 200000),
    }
    assert result.bank_unapplied_minor == {"BANK-1": 50000}
    assert result.payment_statuses == {"ORDER-A": PaymentStatus.FULL, "ORDER-B": PaymentStatus.FULL}
    assert result.kpis["payment_status_counts"]["OVERPAID"] == 0
    assert result.kpis["payment_status_counts"]["FULL"] == 2
    residual = [item for item in result.exceptions if "OVERPAY_RESIDUAL" in item.reason_codes]
    assert len(residual) == 1
    assert residual[0].bank_txn_ids == ("BANK-1",)
    assert residual[0].order_ids == ()
    assert residual[0].risk_amount_minor == 50000
    assert result.conservation.is_valid


@pytest.mark.parametrize("case", cases(), ids=lambda case: case.name)
def test_independent_classification_oracles(case) -> None:
    result = run_case(case)
    observed = {
        order.order_id: result.payment_statuses[order.order_id].value
        if order.order_id in result.payment_statuses
        else "EXCLUDED_FROM_EFFECTIVE_INPUT"
        for order in case.orders
    }
    assert observed == case.expected
    assert result.kpis["confirmed_cash_allocated_minor"] == case.cash
    assert result.kpis["unapplied_bank_credit_minor"] == case.residual
    assert result.conservation.is_valid
    assert set(case.reasons) <= {reason for exception in result.exceptions for reason in exception.reason_codes}
    if case.name == "verified_psp_fee":
        assert sum(item.amount_minor for item in result.adjustments) == 2000
    else:
        assert not result.adjustments
    if case.operation:
        expected = {
            "approve": ("CONFIRMED", "APPROVED"),
            "reject": ("REJECTED", "REJECTED"),
            "undo": ("PROPOSED", "UNDONE"),
        }[case.operation]
        assert {(group.link_status.value, group.review_status.value) for group in result.groups} == {expected}
