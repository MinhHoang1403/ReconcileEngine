"""Strong-reference graph discovery performed before any cash reservation."""

from collections import defaultdict, deque

from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.models import BankTransaction, MatchEvidence, Order
from smartrecon.domain.statuses import AmountBasis, Direction, GroupType
from smartrecon.matching.models import ProposedGroup
from smartrecon.matching.references import extract_known_references, order_reference_index


def discover_strong_reference_groups(
    orders: list[Order],
    banks: list[BankTransaction],
    policy: ReconciliationPolicy,
    excluded_bank_ids: set[str],
) -> tuple[list[ProposedGroup], list[str]]:
    """Build connected reference components and classify safe shapes deterministically."""
    reference_index = order_reference_index(orders)
    known = set(reference_index)
    order_by_id = {order.order_id: order for order in orders}
    bank_by_id = {bank.bank_txn_id: bank for bank in banks}
    order_to_banks: dict[str, set[str]] = defaultdict(set)
    bank_to_orders: dict[str, set[str]] = defaultdict(set)
    collided_banks: list[str] = []

    for bank in banks:
        if (
            bank.bank_txn_id in excluded_bank_ids
            or bank.direction is not Direction.CREDIT
            or bank.amount_basis not in {AmountBasis.POSTED_CASH, AmountBasis.NET_SETTLEMENT}
            or bank.currency is not policy.currency
        ):
            continue
        text = " ".join(value for value in (bank.txn_ref, bank.description, bank.batch_ref) if value)
        hits = extract_known_references(text, known)
        for hit in hits:
            owners = reference_index[hit]
            if len(owners) != 1:
                collided_banks.append(bank.bank_txn_id)
                continue
            order_id = owners[0]
            order_to_banks[order_id].add(bank.bank_txn_id)
            bank_to_orders[bank.bank_txn_id].add(order_id)

    proposals: list[ProposedGroup] = []
    visited_orders: set[str] = set()
    visited_banks: set[str] = set()
    for starting_order in sorted(order_to_banks):
        if starting_order in visited_orders:
            continue
        component_orders: set[str] = set()
        component_banks: set[str] = set()
        queue: deque[tuple[str, str]] = deque([("order", starting_order)])
        while queue:
            kind, identifier = queue.popleft()
            if kind == "order":
                if identifier in component_orders:
                    continue
                component_orders.add(identifier)
                visited_orders.add(identifier)
                queue.extend(("bank", bank_id) for bank_id in order_to_banks[identifier])
            else:
                if identifier in component_banks:
                    continue
                component_banks.add(identifier)
                visited_banks.add(identifier)
                queue.extend(("order", order_id) for order_id in bank_to_orders[identifier])

        order_ids = tuple(sorted(component_orders))
        bank_ids = tuple(sorted(component_banks))
        if len(order_ids) == 1 and len(bank_ids) == 1:
            group_type = GroupType.ONE_TO_ONE
        elif len(order_ids) > 1 and len(bank_ids) == 1:
            group_type = GroupType.MANY_ORDERS_ONE_BANK
        elif len(order_ids) == 1 and len(bank_ids) > 1:
            group_type = GroupType.ONE_ORDER_MANY_BANKS
        else:
            group_type = GroupType.AMBIGUOUS_CANDIDATES

        date_gaps = [
            (bank_by_id[bank_id].value_date or bank_by_id[bank_id].txn_date) - order_by_id[order_id].ordered_at
            for order_id in order_ids
            for bank_id in bank_ids
        ]
        gap_values = [gap.days for gap in date_gaps]
        in_window = all(0 <= gap <= policy.max_days_diff for gap in gap_values)
        currencies_valid = all(order_by_id[order_id].currency is policy.currency for order_id in order_ids)
        complex_many = len(order_ids) > 1 and len(bank_ids) > 1
        auto_confirm = in_window and currencies_valid and not complex_many
        layer = "L1" if not gap_values or max(gap_values) == 0 else "L2"
        reasons = ["FULL_REFERENCE", "NO_REFERENCE_COLLISION"]
        if len(order_ids) > 1:
            reasons.append("MULTI_FULL_REFERENCE")
        if len(bank_ids) > 1:
            reasons.append("SPLIT_FULL_REFERENCE")
        if not in_window:
            reasons.append("OUT_OF_WINDOW")
        if complex_many:
            reasons.append("COMPLEX_MANY_TO_MANY_REVIEW")
        proposals.append(
            ProposedGroup(
                order_ids,
                bank_ids,
                group_type,
                layer,
                MatchEvidence(
                    rule_id=f"{layer}_STRONG_REFERENCE",
                    rule_version=policy.rule_version,
                    reason_codes=tuple(reasons),
                    explanation_vi=(
                        "Tìm thấy mã tham chiếu đầy đủ; cấu trúc và cửa sổ ngày cho phép xác nhận."
                        if auto_confirm
                        else "Có mã tham chiếu nhưng cấu trúc, currency hoặc cửa sổ ngày cần xác minh."
                    ),
                    reference_hits=order_ids,
                    date_delta_days=max(gap_values) if gap_values else None,
                ),
                auto_confirm,
            )
        )

    return proposals, sorted(set(collided_banks))
