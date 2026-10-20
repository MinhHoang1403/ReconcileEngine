"""Adversarial reference oracles independent of matcher suggestions."""

from datetime import date

import pytest

from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.models import BankTransaction, Order
from smartrecon.domain.statuses import AmountBasis, Currency, Direction, LinkStatus
from smartrecon.engine import run_reconciliation
from smartrecon.ingest.normalization import NormalizedBundle


@pytest.mark.parametrize("gap", [0, 1])
@pytest.mark.parametrize("split", [False, True])
def test_unique_reference_cannot_hide_a_colliding_reference_in_the_same_bank_row(gap: int, split: bool) -> None:
    orders = (
        Order("ORDER-A", date(2026, 10, 20), 100000, Currency.VND, external_ref="SHARED-PAYOUT"),
        Order("ORDER-B", date(2026, 10, 20), 200000, Currency.VND, external_ref="SHARED-PAYOUT"),
    )
    banks = (
        BankTransaction(
            bank_txn_id="BANK-1",
            txn_date=date(2026, 10, 20 + gap),
            posted_amount_minor=100000,
            currency=Currency.VND,
            direction=Direction.CREDIT,
            amount_basis=AmountBasis.POSTED_CASH,
            description="ORDER-A SHARED-PAYOUT",
        ),
    )
    if split:
        banks += (
            BankTransaction(
                "BANK-2",
                date(2026, 10, 20 + gap),
                100000,
                Direction.CREDIT,
                AmountBasis.POSTED_CASH,
                Currency.VND,
                description="ORDER-A",
            ),
        )
    result = run_reconciliation(NormalizedBundle(orders, banks, (), (), (), {}), ReconciliationPolicy(Currency.VND))
    assert not result.allocations
    assert not any(group.link_status is LinkStatus.CONFIRMED for group in result.groups)
    assert result.conservation.is_valid
    assert result.bank_unapplied_minor["BANK-1"] == 100000
    if split:
        assert result.bank_unapplied_minor["BANK-2"] == 100000
    strong = [group for group in result.groups if "FULL_REFERENCE" in group.evidence.reason_codes]
    assert strong
    assert all("REFERENCE_COLLISION" in group.evidence.reason_codes for group in strong)
    assert all("NO_REFERENCE_COLLISION" not in group.evidence.reason_codes for group in strong)
