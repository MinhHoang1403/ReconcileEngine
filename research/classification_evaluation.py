"""Independent business-status answers and an offline classification confusion matrix."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from pathlib import Path

from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.models import BankTransaction, Order
from smartrecon.domain.statuses import AmountBasis, Currency, Direction, OrderStatus


@dataclass(frozen=True)
class ClassificationCase:
    name: str
    orders: tuple[Order, ...]
    banks: tuple[BankTransaction, ...]
    expected: dict[str, str]
    cash: int
    residual: int
    reasons: tuple[str, ...] = ()
    operation: str | None = None
    duplicate_ids: tuple[str, ...] = ()
    policy: dict = field(default_factory=dict)


def cases() -> tuple[ClassificationCase, ...]:
    """Answers below are business declarations, never read from matcher output."""
    day = date(2026, 10, 20)
    order = Order("ORDER-A", day, 100000, Currency.VND)
    other = Order("ORDER-B", day, 200000, Currency.VND)
    bank = BankTransaction(
        "BANK-1", day, 100000, Direction.CREDIT, AmountBasis.POSTED_CASH, Currency.VND, description="ORDER-A"
    )
    unidentified = replace(bank, description="Chuyen khoan")
    return (
        ClassificationCase("full", (order,), (bank,), {"ORDER-A": "FULL"}, 100000, 0),
        ClassificationCase(
            "partial",
            (order,),
            (replace(bank, posted_amount_minor=90000),),
            {"ORDER-A": "PARTIAL"},
            90000,
            0,
            ("PARTIAL_PAYMENT",),
        ),
        ClassificationCase(
            "exclusive_overpayment",
            (order,),
            (replace(bank, posted_amount_minor=120000),),
            {"ORDER-A": "OVERPAID"},
            100000,
            20000,
            ("OVERPAY_RESIDUAL",),
        ),
        ClassificationCase(
            "shared_bank_residual",
            (order, other),
            (replace(bank, posted_amount_minor=350000, description="ORDER-A ORDER-B"),),
            {"ORDER-A": "FULL", "ORDER-B": "FULL"},
            300000,
            50000,
            ("OVERPAY_RESIDUAL",),
        ),
        ClassificationCase(
            "unapplied_bank_cash",
            (order,),
            (replace(unidentified, posted_amount_minor=500000),),
            {"ORDER-A": "NO_CONFIRMED_RECEIPT"},
            0,
            500000,
            ("ORPHAN_BANK",),
        ),
        ClassificationCase("unknown_proposal", (order,), (unidentified,), {"ORDER-A": "UNKNOWN"}, 0, 100000),
        ClassificationCase(
            "not_eligible",
            (replace(order, order_status=OrderStatus.CANCELED),),
            (bank,),
            {"ORDER-A": "EXCLUDED_FROM_EFFECTIVE_INPUT"},
            0,
            100000,
        ),
        ClassificationCase(
            "duplicate_import",
            (order,),
            (bank, replace(bank, bank_txn_id="BANK-2")),
            {"ORDER-A": "FULL"},
            100000,
            0,
            ("POSSIBLE_REIMPORT",),
            duplicate_ids=("BANK-2",),
        ),
        ClassificationCase(
            "reference_collision",
            (
                replace(order, external_ref="PAYOUT-1"),
                replace(other, expected_amount_minor=100000, external_ref="PAYOUT-1"),
            ),
            (replace(bank, description="PAYOUT-1"),),
            {"ORDER-A": "UNKNOWN", "ORDER-B": "UNKNOWN"},
            0,
            100000,
            ("REFERENCE_COLLISION",),
        ),
        ClassificationCase(
            "verified_psp_fee",
            (order,),
            (
                replace(
                    bank,
                    posted_amount_minor=98000,
                    amount_basis=AmountBasis.NET_SETTLEMENT,
                    channel="PSP",
                    declared_fee_minor=2000,
                ),
            ),
            {"ORDER-A": "FULL"},
            98000,
            0,
        ),
        ClassificationCase(
            "unverified_fee",
            (order,),
            (replace(bank, posted_amount_minor=98000),),
            {"ORDER-A": "PARTIAL"},
            98000,
            0,
            ("PARTIAL_PAYMENT",),
        ),
        ClassificationCase(
            "search_exhausted",
            (order, replace(other, expected_amount_minor=100000), replace(order, order_id="ORDER-C")),
            (replace(unidentified, posted_amount_minor=1000000),),
            {"ORDER-A": "NO_CONFIRMED_RECEIPT", "ORDER-B": "NO_CONFIRMED_RECEIPT", "ORDER-C": "NO_CONFIRMED_RECEIPT"},
            0,
            1000000,
            ("PARTIAL_SEARCH_EXHAUSTED",),
            policy={"max_group_block_size": 2},
        ),
        ClassificationCase(
            "approved_proposal", (order,), (unidentified,), {"ORDER-A": "FULL"}, 100000, 0, operation="approve"
        ),
        ClassificationCase(
            "rejected_proposal",
            (order,),
            (unidentified,),
            {"ORDER-A": "NO_CONFIRMED_RECEIPT"},
            0,
            100000,
            operation="reject",
        ),
        ClassificationCase(
            "undone_decision", (order,), (unidentified,), {"ORDER-A": "UNKNOWN"}, 0, 100000, operation="undo"
        ),
    )


def run_case(case: ClassificationCase):
    from smartrecon.engine import run_reconciliation
    from smartrecon.ingest.normalization import NormalizedBundle
    from smartrecon.review import approve_group, mark_group_undone, reject_group

    result = run_reconciliation(
        NormalizedBundle(case.orders, case.banks, (), (), case.duplicate_ids, {}),
        ReconciliationPolicy(Currency.VND, **case.policy),
    )
    if case.operation:
        group_id = result.candidates[0].candidate_id
        if case.operation == "approve":
            result = approve_group(result, group_id)
        elif case.operation == "reject":
            result = reject_group(result, group_id)
        elif case.operation == "undo":
            approved = approve_group(result, group_id)
            assert approved.kpis["confirmed_cash_allocated_minor"] == 100000
            # This is the pure restored-snapshot step; HTTP tests cover audit/locking/idempotency.
            result = mark_group_undone(result, group_id)
    return result


def evaluate() -> dict:
    from smartrecon.matching.resolver import derive_payment_statuses

    matrix: Counter[tuple[str, str]] = Counter()
    rows, weighted_error, correct, total = [], 0, 0, 0
    for case in cases():
        result = run_case(case)
        actual = {
            order.order_id: result.payment_statuses[order.order_id].value
            if order.order_id in result.payment_statuses
            else "EXCLUDED_FROM_EFFECTIVE_INPUT"
            for order in case.orders
        }
        for order in case.orders:
            expected, observed = case.expected[order.order_id], actual[order.order_id]
            matrix[(expected, observed)] += 1
            total += 1
            correct += expected == observed
            if expected != observed:
                weighted_error += order.expected_amount_minor
        rows.append(
            {
                "case": case.name,
                "expected": case.expected,
                "actual": actual,
                "cash_minor": result.kpis["confirmed_cash_allocated_minor"],
                "residual_minor": result.kpis["unapplied_bank_credit_minor"],
                "expected_cash_minor": case.cash,
                "expected_residual_minor": case.residual,
                "conservation": result.conservation.is_valid,
                "link_review_states": sorted(
                    {(group.link_status.value, group.review_status.value) for group in result.groups}
                ),
            }
        )
    implementation = Path(inspect.getfile(derive_payment_statuses)).resolve()
    return {
        "cases": rows,
        "correct": correct,
        "total": total,
        "accuracy": correct / total,
        "amount_weighted_misclassification_minor": weighted_error,
        "confusion_matrix": [
            {"expected": expected, "observed": observed, "count": count}
            for (expected, observed), count in sorted(matrix.items())
        ],
        "exclusion_semantics": "Ineligible source rows are excluded, not returned as an effective API order",
        "implementation_file": str(implementation),
        "implementation_sha256": hashlib.sha256(implementation.read_bytes()).hexdigest(),
        "source_commit": subprocess.check_output(
            ["git", "-C", str(implementation.parents[3]), "rev-parse", "HEAD"], text=True
        ).strip(),
        "case_hash": hashlib.sha256(
            json.dumps([asdict(case) for case in cases()], sort_keys=True, default=str).encode()
        ).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}))


if __name__ == "__main__":
    main()
