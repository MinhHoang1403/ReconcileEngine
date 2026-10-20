"""Pure review decisions over an effective reconciliation snapshot."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from smartrecon.analytics.metrics import calculate_kpis
from smartrecon.domain.invariants import check_conservation
from smartrecon.domain.models import (
    AllocationEdge,
    BankTransaction,
    Candidate,
    ExceptionCase,
    MatchGroup,
)
from smartrecon.domain.statuses import (
    AmountBasis,
    Direction,
    GroupType,
    LinkStatus,
    OrderStatus,
    PaymentStatus,
    ReviewStatus,
)
from smartrecon.engine import ReconciliationResult
from smartrecon.matching.resolver import derive_payment_statuses, stable_id


class ReviewDecisionError(ValueError):
    """A review command that cannot safely change the effective snapshot."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def approve_group(result: ReconciliationResult, group_id: str) -> ReconciliationResult:
    """Approve one proposed 1:1, N:1, or 1:N group without creating adjustments."""
    target = _reviewable_group(result, group_id)
    if target.group_type is GroupType.AMBIGUOUS_CANDIDATES or (
        len(target.order_ids) > 1 and len(target.bank_txn_ids) > 1
    ):
        raise ReviewDecisionError(
            "COMPLEX_GROUP_NOT_APPROVABLE",
            "Nhóm M:N phức tạp không thể được chấp thuận tự động trong phạm vi hiện tại.",
        )

    order_by_id = {order.order_id: order for order in result.orders}
    bank_by_id = {bank.bank_txn_id: bank for bank in result.bank_transactions}
    existing_order_ids = {edge.order_id for edge in result.allocations}
    existing_bank_ids = {edge.bank_txn_id for edge in result.allocations}
    if set(target.order_ids) & existing_order_ids or set(target.bank_txn_ids) & existing_bank_ids:
        raise ReviewDecisionError(
            "ALLOCATION_CONFLICT",
            "Một đơn hàng hoặc giao dịch trong đề xuất đã có phân bổ hiệu lực.",
        )

    try:
        orders = [order_by_id[order_id] for order_id in target.order_ids]
        banks = [bank_by_id[bank_id] for bank_id in target.bank_txn_ids]
    except KeyError as exc:
        raise ReviewDecisionError("REVIEW_SOURCE_MISSING", "Không tìm thấy bản ghi nguồn của đề xuất.") from exc

    currencies = {item.currency for item in [*orders, *banks]}
    if len(currencies) != 1:
        raise ReviewDecisionError("CURRENCY_MISMATCH", "Không thể duyệt nhóm có nhiều loại tiền.")
    if any(order.order_status is not OrderStatus.ELIGIBLE for order in orders):
        raise ReviewDecisionError("ORDER_NOT_ELIGIBLE", "Nhóm chứa khoản phải thu không đủ điều kiện.")
    if any(
        bank.direction is not Direction.CREDIT
        or bank.amount_basis not in {AmountBasis.POSTED_CASH, AmountBasis.NET_SETTLEMENT}
        for bank in banks
    ):
        raise ReviewDecisionError("BANK_NOT_ELIGIBLE", "Nhóm chứa giao dịch không thuộc cash credit hợp lệ.")

    order_remaining = {order.order_id: order.expected_amount_minor for order in orders}
    bank_remaining = {bank.bank_txn_id: bank.eligible_credit_minor for bank in banks}
    new_edges: list[AllocationEdge] = []
    for bank in banks:
        for order in orders:
            allocated = min(bank_remaining[bank.bank_txn_id], order_remaining[order.order_id])
            if allocated <= 0:
                continue
            new_edges.append(
                AllocationEdge(
                    edge_id=stable_id("EDGE", (order.order_id,), (bank.bank_txn_id,)),
                    group_id=target.group_id,
                    order_id=order.order_id,
                    bank_txn_id=bank.bank_txn_id,
                    allocated_cash_minor=allocated,
                    currency=order.currency,
                )
            )
            bank_remaining[bank.bank_txn_id] -= allocated
            order_remaining[order.order_id] -= allocated

    if not new_edges:
        raise ReviewDecisionError("NO_ALLOCATABLE_CASH", "Đề xuất không còn số tiền hợp lệ để phân bổ.")

    groups = tuple(
        replace(group, link_status=LinkStatus.CONFIRMED, review_status=ReviewStatus.APPROVED)
        if group.group_id == group_id
        else group
        for group in result.groups
    )
    candidates = tuple(candidate for candidate in result.candidates if candidate.candidate_id != group_id)
    return _rebuild(result, groups, result.allocations + tuple(new_edges), candidates)


def reject_group(result: ReconciliationResult, group_id: str) -> ReconciliationResult:
    """Reject one proposal while retaining its evidence and all existing cash allocations."""
    _reviewable_group(result, group_id)
    groups = tuple(
        replace(group, link_status=LinkStatus.REJECTED, review_status=ReviewStatus.REJECTED)
        if group.group_id == group_id
        else group
        for group in result.groups
    )
    candidates = tuple(candidate for candidate in result.candidates if candidate.candidate_id != group_id)
    return _rebuild(result, groups, result.allocations, candidates)


def mark_group_undone(result: ReconciliationResult, group_id: str | None) -> ReconciliationResult:
    """Mark a restored proposal as undone while keeping it available for a later decision."""
    if group_id is None:
        return result
    target = next((group for group in result.groups if group.group_id == group_id), None)
    if target is None or target.link_status is not LinkStatus.PROPOSED:
        raise ReviewDecisionError(
            "UNDO_SNAPSHOT_INVALID",
            "Snapshot trước quyết định không còn proposal cần hoàn tác.",
        )
    groups = tuple(
        replace(group, review_status=ReviewStatus.UNDONE) if group.group_id == group_id else group
        for group in result.groups
    )
    return replace(result, groups=groups)


def _reviewable_group(result: ReconciliationResult, group_id: str) -> MatchGroup:
    target = next((group for group in result.groups if group.group_id == group_id), None)
    if target is None:
        raise ReviewDecisionError("REVIEW_GROUP_NOT_FOUND", "Không tìm thấy đề xuất cần xác minh.")
    if target.link_status is not LinkStatus.PROPOSED or target.review_status not in {
        ReviewStatus.OPEN,
        ReviewStatus.UNDONE,
    }:
        raise ReviewDecisionError("REVIEW_GROUP_NOT_OPEN", "Đề xuất không còn ở trạng thái chờ xác minh.")
    return target


def _eligible_banks(result: ReconciliationResult) -> list[BankTransaction]:
    duplicate_bank_ids = {
        bank_id
        for exception in result.exceptions
        if "POSSIBLE_REIMPORT" in exception.reason_codes
        for bank_id in exception.bank_txn_ids
    }
    currency = result.orders[0].currency if result.orders else None
    return [
        bank
        for bank in result.bank_transactions
        if bank.bank_txn_id not in duplicate_bank_ids
        and bank.direction is Direction.CREDIT
        and bank.amount_basis in {AmountBasis.POSTED_CASH, AmountBasis.NET_SETTLEMENT}
        and (currency is None or bank.currency is currency)
    ]


def _rebuild(
    result: ReconciliationResult,
    groups: tuple[MatchGroup, ...],
    allocations: tuple[AllocationEdge, ...],
    candidates: tuple[Candidate, ...],
) -> ReconciliationResult:
    orders = list(result.orders)
    eligible_banks = _eligible_banks(result)
    confirmed_bank_ids = {edge.bank_txn_id for edge in allocations}
    statuses = derive_payment_statuses(
        orders,
        eligible_banks,
        list(allocations),
        list(result.adjustments),
        list(candidates),
        confirmed_bank_ids,
        groups,
    )
    groups = tuple(
        replace(
            group,
            payment_statuses={order_id: statuses[order_id] for order_id in group.order_ids if order_id in statuses},
        )
        for group in groups
    )
    conservation = check_conservation(
        orders,
        eligible_banks,
        list(allocations),
        list(result.adjustments),
    )
    if not conservation.is_valid:
        raise ReviewDecisionError(
            "MONEY_INVARIANT_VIOLATION",
            f"Thao tác vi phạm bất biến tiền: {', '.join(conservation.violations)}",
        )
    exceptions = _effective_exceptions(result, statuses, allocations, candidates, confirmed_bank_ids, eligible_banks)
    kpis = calculate_kpis(
        orders,
        eligible_banks,
        list(groups),
        list(allocations),
        list(result.adjustments),
        list(exceptions),
    )
    return replace(
        result,
        groups=groups,
        allocations=allocations,
        candidates=candidates,
        exceptions=exceptions,
        payment_statuses=statuses,
        bank_unapplied_minor=conservation.bank_unapplied,
        order_outstanding_minor=conservation.order_outstanding,
        kpis=kpis,
        layer_counts=_layer_counts(groups),
        conservation=conservation,
    )


def _effective_exceptions(
    base: ReconciliationResult,
    statuses: dict[str, PaymentStatus],
    allocations: tuple[AllocationEdge, ...],
    candidates: tuple[Candidate, ...],
    confirmed_bank_ids: set[str],
    eligible_banks: list[BankTransaction],
) -> tuple[ExceptionCase, ...]:
    static_reasons = {
        "POSSIBLE_REIMPORT",
        "DEBIT_EXCLUDED",
        "CURRENCY_MISMATCH",
        "REFERENCE_COLLISION",
        "PARTIAL_SEARCH_EXHAUSTED",
    }
    exceptions = [exception for exception in base.exceptions if set(exception.reason_codes) & static_reasons]
    allocated_by_order: defaultdict[str, int] = defaultdict(int)
    adjusted_by_order: defaultdict[str, int] = defaultdict(int)
    allocated_by_bank: defaultdict[str, int] = defaultdict(int)
    for edge in allocations:
        allocated_by_order[edge.order_id] += edge.allocated_cash_minor
        allocated_by_bank[edge.bank_txn_id] += edge.allocated_cash_minor
    for adjustment in base.adjustments:
        adjusted_by_order[adjustment.order_id] += adjustment.amount_minor

    proposed_orders = {order_id for candidate in candidates for order_id in candidate.order_ids}
    proposed_banks = {bank_id for candidate in candidates for bank_id in candidate.bank_txn_ids}
    for order in base.orders:
        status = statuses[order.order_id]
        if status is PaymentStatus.PARTIAL:
            exceptions.append(
                ExceptionCase(
                    f"EXC-PARTIAL-{order.order_id}",
                    ("PARTIAL_PAYMENT",),
                    (order.order_id,),
                    risk_amount_minor=(
                        order.expected_amount_minor
                        - allocated_by_order[order.order_id]
                        - adjusted_by_order[order.order_id]
                    ),
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
        unapplied = bank.eligible_credit_minor - allocated_by_bank[bank.bank_txn_id]
        if unapplied <= 0:
            continue
        reason = "PROPOSED_BANK" if bank.bank_txn_id in proposed_banks else "ORPHAN_BANK"
        if bank.bank_txn_id in confirmed_bank_ids:
            reason = "OVERPAY_RESIDUAL"
        exceptions.append(
            ExceptionCase(
                f"EXC-BANK-{bank.bank_txn_id}",
                (reason,),
                bank_txn_ids=(bank.bank_txn_id,),
                risk_amount_minor=unapplied,
            )
        )
    for candidate in candidates:
        if "COMPLEX_MANY_TO_MANY_REVIEW" in candidate.evidence.reason_codes:
            exceptions.append(
                ExceptionCase(
                    f"EXC-COMPLEX-{candidate.candidate_id}",
                    ("COMPLEX_MANY_TO_MANY_REVIEW",),
                    candidate.order_ids,
                    candidate.bank_txn_ids,
                )
            )
    return tuple(sorted(exceptions, key=lambda item: item.exception_id))


def _layer_counts(groups: tuple[MatchGroup, ...]) -> dict[str, dict[str, int]]:
    counts = {layer: {"confirmed_groups": 0, "proposed_groups": 0} for layer in ("L1", "L2", "L3", "L4")}
    for group in groups:
        layer = group.evidence.rule_id.split("_", 1)[0]
        if layer not in counts:
            continue
        if group.link_status is LinkStatus.CONFIRMED:
            counts[layer]["confirmed_groups"] += 1
        elif group.link_status is LinkStatus.PROPOSED:
            counts[layer]["proposed_groups"] += 1
    return counts
