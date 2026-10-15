"""Deterministic conflict annotation and conservation-safe confirmed allocation."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass

from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.models import (
    AllocationEdge,
    BankTransaction,
    Candidate,
    MatchGroup,
    Order,
    VerifiedAdjustment,
)
from smartrecon.domain.statuses import (
    AmountBasis,
    LinkStatus,
    PaymentStatus,
    ReviewStatus,
)
from smartrecon.matching.models import ProposedGroup


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    groups: tuple[MatchGroup, ...]
    allocations: tuple[AllocationEdge, ...]
    adjustments: tuple[VerifiedAdjustment, ...]
    candidates: tuple[Candidate, ...]
    confirmed_order_ids: frozenset[str]
    confirmed_bank_ids: frozenset[str]


def stable_id(prefix: str, order_ids: tuple[str, ...], bank_ids: tuple[str, ...]) -> str:
    payload = f"{prefix}|{','.join(order_ids)}|{','.join(bank_ids)}"
    return f"{prefix}-{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def resolve_groups(
    proposals: list[ProposedGroup],
    orders: list[Order],
    banks: list[BankTransaction],
    policy: ReconciliationPolicy,
) -> ResolutionResult:
    """Commit only non-overlapping auto groups; all other proposals remain non-effective."""
    order_by_id = {order.order_id: order for order in orders}
    bank_by_id = {bank.bank_txn_id: bank for bank in banks}
    confirmed_orders: set[str] = set()
    confirmed_banks: set[str] = set()
    groups: list[MatchGroup] = []
    allocations: list[AllocationEdge] = []
    adjustments: list[VerifiedAdjustment] = []
    pending: list[ProposedGroup] = []

    unique: dict[tuple[tuple[str, ...], tuple[str, ...]], ProposedGroup] = {}
    # L3 carries identity-like text evidence and should represent a duplicate
    # proposed pair instead of the weaker amount/date-only L2 candidate.
    layer_rank = {"L1": 4, "L3": 3, "L2": 2, "L4": 1}
    for proposal in proposals:
        existing = unique.get(proposal.participant_key)
        if existing is None or layer_rank[proposal.layer] > layer_rank[existing.layer]:
            unique[proposal.participant_key] = proposal

    ordered = sorted(
        unique.values(),
        key=lambda item: (-int(item.auto_confirm), -layer_rank[item.layer], item.participant_key),
    )
    for proposal in ordered:
        participant_conflict = bool(set(proposal.order_ids) & confirmed_orders) or bool(
            set(proposal.bank_txn_ids) & confirmed_banks
        )
        if not proposal.auto_confirm or participant_conflict:
            pending.append(proposal)
            continue

        group_id = stable_id("GRP", proposal.order_ids, proposal.bank_txn_ids)
        group_edges, group_adjustments = _allocate_confirmed_group(group_id, proposal, order_by_id, bank_by_id, policy)
        allocations.extend(group_edges)
        adjustments.extend(group_adjustments)
        confirmed_orders.update(proposal.order_ids)
        confirmed_banks.update(proposal.bank_txn_ids)
        groups.append(
            MatchGroup(
                group_id=group_id,
                group_type=proposal.group_type,
                order_ids=proposal.order_ids,
                bank_txn_ids=proposal.bank_txn_ids,
                link_status=LinkStatus.CONFIRMED,
                review_status=ReviewStatus.NOT_REQUIRED,
                payment_statuses={},
                evidence=proposal.evidence,
            )
        )

    candidates = _annotate_conflicts(pending)
    for candidate in candidates:
        groups.append(
            MatchGroup(
                group_id=candidate.candidate_id,
                group_type=candidate.group_type,
                order_ids=candidate.order_ids,
                bank_txn_ids=candidate.bank_txn_ids,
                link_status=LinkStatus.PROPOSED,
                review_status=ReviewStatus.OPEN,
                payment_statuses={order_id: PaymentStatus.UNKNOWN for order_id in candidate.order_ids},
                evidence=candidate.evidence,
            )
        )

    payment_statuses = derive_payment_statuses(orders, banks, allocations, adjustments, candidates, confirmed_banks)
    groups = [
        MatchGroup(
            group_id=group.group_id,
            group_type=group.group_type,
            order_ids=group.order_ids,
            bank_txn_ids=group.bank_txn_ids,
            link_status=group.link_status,
            review_status=group.review_status,
            payment_statuses={
                order_id: payment_statuses[order_id] for order_id in group.order_ids if order_id in payment_statuses
            },
            evidence=group.evidence,
        )
        for group in groups
    ]
    return ResolutionResult(
        tuple(groups),
        tuple(allocations),
        tuple(adjustments),
        tuple(candidates),
        frozenset(confirmed_orders),
        frozenset(confirmed_banks),
    )


def _allocate_confirmed_group(
    group_id: str,
    proposal: ProposedGroup,
    order_by_id: dict[str, Order],
    bank_by_id: dict[str, BankTransaction],
    policy: ReconciliationPolicy,
) -> tuple[list[AllocationEdge], list[VerifiedAdjustment]]:
    order_remaining = {order_id: order_by_id[order_id].expected_amount_minor for order_id in proposal.order_ids}
    bank_remaining = {bank_id: bank_by_id[bank_id].eligible_credit_minor for bank_id in proposal.bank_txn_ids}
    edges: list[AllocationEdge] = []
    for bank_id in proposal.bank_txn_ids:
        for order_id in proposal.order_ids:
            allocated = min(bank_remaining[bank_id], order_remaining[order_id])
            if allocated <= 0:
                continue
            edge_id = stable_id("EDGE", (order_id,), (bank_id,))
            edges.append(
                AllocationEdge(
                    edge_id,
                    group_id,
                    order_id,
                    bank_id,
                    allocated,
                    policy.currency,
                )
            )
            bank_remaining[bank_id] -= allocated
            order_remaining[order_id] -= allocated

    adjustments: list[VerifiedAdjustment] = []
    if len(proposal.order_ids) == 1 and len(proposal.bank_txn_ids) == 1:
        order_id = proposal.order_ids[0]
        bank = bank_by_id[proposal.bank_txn_ids[0]]
        residual = order_remaining[order_id]
        if (
            policy.allow_verified_psp_fees
            and residual > 0
            and bank.amount_basis is AmountBasis.NET_SETTLEMENT
            and bank.channel == "PSP"
            and bank.declared_fee_minor == residual
        ):
            adjustments.append(
                VerifiedAdjustment(
                    stable_id("ADJ", (order_id,), (bank.bank_txn_id,)),
                    order_id,
                    residual,
                    "PSP_FEE",
                    f"declared_fee:{bank.bank_txn_id}",
                )
            )
    return edges, adjustments


def _annotate_conflicts(proposals: list[ProposedGroup]) -> list[Candidate]:
    proposal_ids = [stable_id("CAND", proposal.order_ids, proposal.bank_txn_ids) for proposal in proposals]
    conflicts: dict[str, set[str]] = defaultdict(set)
    for index, left in enumerate(proposals):
        for other_index, right in enumerate(proposals[index + 1 :], start=index + 1):
            if set(left.order_ids) & set(right.order_ids) or set(left.bank_txn_ids) & set(right.bank_txn_ids):
                conflicts[proposal_ids[index]].add(proposal_ids[other_index])
                conflicts[proposal_ids[other_index]].add(proposal_ids[index])
    return [
        Candidate(
            proposal_ids[index],
            proposal.order_ids,
            proposal.bank_txn_ids,
            proposal.group_type,
            proposal.evidence,
            tuple(sorted(conflicts[proposal_ids[index]])),
        )
        for index, proposal in enumerate(proposals)
    ]


def derive_payment_statuses(
    orders: list[Order],
    banks: list[BankTransaction],
    allocations: list[AllocationEdge],
    adjustments: list[VerifiedAdjustment],
    candidates: list[Candidate] | tuple[Candidate, ...],
    confirmed_bank_ids: set[str] | frozenset[str],
) -> dict[str, PaymentStatus]:
    by_order: defaultdict[str, int] = defaultdict(int)
    adjusted: defaultdict[str, int] = defaultdict(int)
    by_bank: defaultdict[str, int] = defaultdict(int)
    order_banks: defaultdict[str, set[str]] = defaultdict(set)
    for edge in allocations:
        by_order[edge.order_id] += edge.allocated_cash_minor
        by_bank[edge.bank_txn_id] += edge.allocated_cash_minor
        order_banks[edge.order_id].add(edge.bank_txn_id)
    for adjustment in adjustments:
        adjusted[adjustment.order_id] += adjustment.amount_minor
    bank_by_id = {bank.bank_txn_id: bank for bank in banks}
    proposed_orders = {order_id for candidate in candidates for order_id in candidate.order_ids}
    statuses: dict[str, PaymentStatus] = {}
    for order in orders:
        fulfilled = by_order[order.order_id] + adjusted[order.order_id]
        if fulfilled == 0:
            statuses[order.order_id] = (
                PaymentStatus.UNKNOWN if order.order_id in proposed_orders else PaymentStatus.NO_CONFIRMED_RECEIPT
            )
        elif fulfilled < order.expected_amount_minor:
            statuses[order.order_id] = PaymentStatus.PARTIAL
        else:
            has_excess = any(
                bank_by_id[bank_id].eligible_credit_minor > by_bank[bank_id]
                for bank_id in order_banks[order.order_id]
                if bank_id in confirmed_bank_ids
            )
            statuses[order.order_id] = PaymentStatus.OVERPAID if has_excess else PaymentStatus.FULL
    return statuses
