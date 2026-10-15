"""Public reconciliation API shared by HTTP orchestration, tests, and research clients."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any

from smartrecon.analytics.metrics import calculate_kpis
from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.invariants import ConservationReport, check_conservation
from smartrecon.domain.models import (
    AllocationEdge,
    BankTransaction,
    Candidate,
    ExceptionCase,
    MatchGroup,
    Order,
    VerifiedAdjustment,
)
from smartrecon.domain.statuses import (
    AmountBasis,
    Direction,
    LinkStatus,
    OrderStatus,
    PaymentStatus,
)
from smartrecon.ingest.normalization import NormalizedBundle
from smartrecon.matching.constrained import amount_date_candidates
from smartrecon.matching.fuzzy import fuzzy_candidates
from smartrecon.matching.grouping import bounded_group_candidates
from smartrecon.matching.reference import discover_strong_reference_groups
from smartrecon.matching.resolver import ResolutionResult, resolve_groups


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    orders: tuple[Order, ...]
    bank_transactions: tuple[BankTransaction, ...]
    groups: tuple[MatchGroup, ...]
    allocations: tuple[AllocationEdge, ...]
    adjustments: tuple[VerifiedAdjustment, ...]
    candidates: tuple[Candidate, ...]
    exceptions: tuple[ExceptionCase, ...]
    payment_statuses: dict[str, PaymentStatus]
    bank_unapplied_minor: dict[str, int]
    order_outstanding_minor: dict[str, int]
    kpis: dict[str, Any]
    layer_counts: dict[str, dict[str, int]]
    conservation: ConservationReport
    semantic_checksum: str


def run_reconciliation(
    inputs: NormalizedBundle,
    policy: ReconciliationPolicy,
) -> ReconciliationResult:
    """Run four evidence layers, resolve conflicts, allocate cash, and verify invariants."""
    orders = [order for order in inputs.orders if order.order_status is OrderStatus.ELIGIBLE]
    all_banks = list(inputs.bank_transactions)
    duplicate_ids = set(inputs.duplicate_bank_ids)
    eligible_banks = [
        bank
        for bank in all_banks
        if bank.bank_txn_id not in duplicate_ids
        and bank.direction is Direction.CREDIT
        and bank.amount_basis in {AmountBasis.POSTED_CASH, AmountBasis.NET_SETTLEMENT}
        and bank.currency is policy.currency
    ]

    strong, collided_banks = discover_strong_reference_groups(orders, all_banks, policy, duplicate_ids)
    preconfirmed_order_ids = {
        order_id for proposal in strong if proposal.auto_confirm for order_id in proposal.order_ids
    }
    preconfirmed_bank_ids = {
        bank_id for proposal in strong if proposal.auto_confirm for bank_id in proposal.bank_txn_ids
    }
    remaining_orders = [order for order in orders if order.order_id not in preconfirmed_order_ids]
    remaining_banks = [bank for bank in eligible_banks if bank.bank_txn_id not in preconfirmed_bank_ids]
    constrained = amount_date_candidates(remaining_orders, remaining_banks, policy)
    fuzzy = fuzzy_candidates(remaining_orders, remaining_banks, policy)
    grouped, search_exhausted = bounded_group_candidates(remaining_orders, remaining_banks, policy)
    resolution = resolve_groups(strong + constrained + fuzzy + grouped, orders, eligible_banks, policy)
    exceptions = _classify_exceptions(
        orders,
        all_banks,
        eligible_banks,
        duplicate_ids,
        collided_banks,
        resolution,
        search_exhausted,
    )
    conservation = check_conservation(
        orders,
        eligible_banks,
        list(resolution.allocations),
        list(resolution.adjustments),
    )
    if not conservation.is_valid:
        raise RuntimeError(f"Vi phạm bất biến tiền: {', '.join(conservation.violations)}")

    payment_statuses = _collect_payment_statuses(orders, resolution.groups)
    kpis = calculate_kpis(
        orders,
        eligible_banks,
        list(resolution.groups),
        list(resolution.allocations),
        list(resolution.adjustments),
        exceptions,
    )
    layer_counts = _layer_counts(resolution.groups)
    checksum = _semantic_checksum(orders, eligible_banks, resolution, exceptions, kpis, policy)
    return ReconciliationResult(
        tuple(orders),
        tuple(all_banks),
        resolution.groups,
        resolution.allocations,
        resolution.adjustments,
        resolution.candidates,
        tuple(exceptions),
        payment_statuses,
        conservation.bank_unapplied,
        conservation.order_outstanding,
        kpis,
        layer_counts,
        conservation,
        checksum,
    )


def _collect_payment_statuses(orders: list[Order], groups: tuple[MatchGroup, ...]) -> dict[str, PaymentStatus]:
    statuses = {order.order_id: PaymentStatus.NO_CONFIRMED_RECEIPT for order in orders}
    for group in groups:
        for order_id, status in group.payment_statuses.items():
            if group.link_status is LinkStatus.CONFIRMED or statuses[order_id] is PaymentStatus.NO_CONFIRMED_RECEIPT:
                statuses[order_id] = status
    return statuses


def _classify_exceptions(
    orders: list[Order],
    all_banks: list[BankTransaction],
    eligible_banks: list[BankTransaction],
    duplicate_ids: set[str],
    collided_banks: list[str],
    resolution: ResolutionResult,
    search_exhausted: bool,
) -> list[ExceptionCase]:
    exceptions: list[ExceptionCase] = []
    statuses = _collect_payment_statuses(orders, resolution.groups)
    allocation_by_bank: defaultdict[str, int] = defaultdict(int)
    allocation_by_order: defaultdict[str, int] = defaultdict(int)
    adjustment_by_order: defaultdict[str, int] = defaultdict(int)
    for edge in resolution.allocations:
        allocation_by_bank[edge.bank_txn_id] += edge.allocated_cash_minor
        allocation_by_order[edge.order_id] += edge.allocated_cash_minor
    for adjustment in resolution.adjustments:
        adjustment_by_order[adjustment.order_id] += adjustment.amount_minor

    proposed_orders = {order_id for item in resolution.candidates for order_id in item.order_ids}
    proposed_banks = {bank_id for item in resolution.candidates for bank_id in item.bank_txn_ids}
    for order in orders:
        status = statuses[order.order_id]
        if status is PaymentStatus.PARTIAL:
            exceptions.append(
                ExceptionCase(
                    f"EXC-PARTIAL-{order.order_id}",
                    ("PARTIAL_PAYMENT",),
                    (order.order_id,),
                    risk_amount_minor=order.expected_amount_minor
                    - allocation_by_order[order.order_id]
                    - adjustment_by_order[order.order_id],
                )
            )
        elif status in {PaymentStatus.NO_CONFIRMED_RECEIPT, PaymentStatus.UNKNOWN}:
            reason = "AMBIGUOUS_CANDIDATES" if order.order_id in proposed_orders else "NO_CONFIRMED_RECEIPT"
            exceptions.append(
                ExceptionCase(
                    f"EXC-ORDER-{order.order_id}",
                    (reason,),
                    (order.order_id,),
                    risk_amount_minor=order.expected_amount_minor,
                )
            )

    for bank in eligible_banks:
        unapplied = bank.eligible_credit_minor - allocation_by_bank[bank.bank_txn_id]
        if unapplied > 0:
            reason = "PROPOSED_BANK" if bank.bank_txn_id in proposed_banks else "ORPHAN_BANK"
            if bank.bank_txn_id in resolution.confirmed_bank_ids:
                reason = "OVERPAY_RESIDUAL"
            exceptions.append(
                ExceptionCase(
                    f"EXC-BANK-{bank.bank_txn_id}",
                    (reason,),
                    bank_txn_ids=(bank.bank_txn_id,),
                    risk_amount_minor=unapplied,
                )
            )

    for bank in all_banks:
        if bank.bank_txn_id in duplicate_ids:
            exceptions.append(
                ExceptionCase(
                    f"EXC-DUP-{bank.bank_txn_id}",
                    ("POSSIBLE_REIMPORT",),
                    bank_txn_ids=(bank.bank_txn_id,),
                    risk_amount_minor=bank.posted_amount_minor,
                )
            )
        elif bank.direction is Direction.DEBIT:
            exceptions.append(
                ExceptionCase(
                    f"EXC-DEBIT-{bank.bank_txn_id}",
                    ("DEBIT_EXCLUDED",),
                    bank_txn_ids=(bank.bank_txn_id,),
                    risk_amount_minor=bank.posted_amount_minor,
                )
            )
        elif bank.currency != (orders[0].currency if orders else bank.currency):
            exceptions.append(
                ExceptionCase(
                    f"EXC-CURRENCY-{bank.bank_txn_id}",
                    ("CURRENCY_MISMATCH",),
                    bank_txn_ids=(bank.bank_txn_id,),
                    risk_amount_minor=bank.posted_amount_minor,
                )
            )
    for bank_id in collided_banks:
        exceptions.append(
            ExceptionCase(
                f"EXC-REF-COLLISION-{bank_id}",
                ("REFERENCE_COLLISION",),
                bank_txn_ids=(bank_id,),
            )
        )
    for candidate in resolution.candidates:
        if "COMPLEX_MANY_TO_MANY_REVIEW" in candidate.evidence.reason_codes:
            exceptions.append(
                ExceptionCase(
                    f"EXC-COMPLEX-{candidate.candidate_id}",
                    ("COMPLEX_MANY_TO_MANY_REVIEW",),
                    candidate.order_ids,
                    candidate.bank_txn_ids,
                )
            )
    if search_exhausted:
        exceptions.append(ExceptionCase("EXC-SEARCH-BUDGET", ("PARTIAL_SEARCH_EXHAUSTED",)))
    return sorted(exceptions, key=lambda item: item.exception_id)


def _layer_counts(groups: tuple[MatchGroup, ...]) -> dict[str, dict[str, int]]:
    counts = {layer: {"confirmed_groups": 0, "proposed_groups": 0} for layer in ("L1", "L2", "L3", "L4")}
    for group in groups:
        layer = group.evidence.rule_id.split("_", 1)[0]
        key = "confirmed_groups" if group.link_status is LinkStatus.CONFIRMED else "proposed_groups"
        counts[layer][key] += 1
    return counts


def _semantic_checksum(
    orders: list[Order],
    banks: list[BankTransaction],
    resolution: ResolutionResult,
    exceptions: list[ExceptionCase],
    kpis: dict[str, Any],
    policy: ReconciliationPolicy,
) -> str:
    def clean(record: Any) -> Any:
        payload = asdict(record)
        payload.pop("lineage", None)
        return payload

    policy_payload = asdict(policy)
    # JSON distinguishes 85 from 85.0 even though the policy does not. Normalize
    # the sole floating threshold so semantically identical callers hash alike.
    policy_payload["fuzzy_candidate_threshold"] = float(policy.fuzzy_candidate_threshold)
    payload = {
        "orders": [clean(item) for item in sorted(orders, key=lambda row: row.order_id)],
        "banks": [clean(item) for item in sorted(banks, key=lambda row: row.bank_txn_id)],
        "groups": [clean(item) for item in resolution.groups],
        "allocations": [clean(item) for item in resolution.allocations],
        "adjustments": [clean(item) for item in resolution.adjustments],
        "exceptions": [clean(item) for item in exceptions],
        "kpis": kpis,
        "policy": policy_payload,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()
