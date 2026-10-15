"""Bounded subset proposals for N:1 and 1:N without sufficient identity evidence."""

from itertools import combinations

from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.models import BankTransaction, MatchEvidence, Order
from smartrecon.domain.statuses import GroupType
from smartrecon.matching.models import ProposedGroup


def bounded_group_candidates(
    orders: list[Order], banks: list[BankTransaction], policy: ReconciliationPolicy
) -> tuple[list[ProposedGroup], bool]:
    """Return review-only exact-sum subsets and whether any search budget was exhausted."""
    candidates: list[ProposedGroup] = []
    exhausted = False
    sorted_orders = sorted(orders, key=lambda row: row.order_id)
    sorted_banks = sorted(banks, key=lambda row: row.bank_txn_id)

    for bank in sorted_banks:
        block = [
            order
            for order in sorted_orders
            if order.currency is bank.currency
            and order.currency is policy.currency
            and 0 <= ((bank.value_date or bank.txn_date) - order.ordered_at).days <= policy.max_days_diff
            and order.expected_amount_minor <= bank.eligible_credit_minor
        ]
        if len(block) > policy.max_group_block_size:
            exhausted = True
            continue
        checked = 0
        for size in range(2, min(policy.max_group_orders, len(block)) + 1):
            for subset in combinations(block, size):
                checked += 1
                if checked > policy.max_combinations_per_case:
                    exhausted = True
                    break
                if sum(order.expected_amount_minor for order in subset) != bank.eligible_credit_minor:
                    continue
                candidates.append(
                    ProposedGroup(
                        tuple(order.order_id for order in subset),
                        (bank.bank_txn_id,),
                        GroupType.MANY_ORDERS_ONE_BANK,
                        "L4",
                        MatchEvidence(
                            rule_id="L4_BOUNDED_GROUP_CANDIDATE",
                            rule_version=policy.rule_version,
                            reason_codes=("EXACT_SUBSET_SUM", "IDENTITY_EVIDENCE_MISSING"),
                            explanation_vi=(
                                "Tổng một nhóm đơn bằng tiền bank nhưng thiếu mã tham chiếu; chỉ đề xuất xác minh."
                            ),
                            amount_delta_minor=0,
                        ),
                        False,
                    )
                )
            if checked > policy.max_combinations_per_case:
                break

    for order in sorted_orders:
        block = [
            bank
            for bank in sorted_banks
            if order.currency is bank.currency
            and order.currency is policy.currency
            and bank.eligible_credit_minor > 0
            and 0 <= ((bank.value_date or bank.txn_date) - order.ordered_at).days <= policy.max_days_diff
            and bank.eligible_credit_minor <= order.expected_amount_minor
        ]
        if len(block) > policy.max_group_block_size:
            exhausted = True
            continue
        checked = 0
        for size in range(2, min(policy.max_split_bank_rows, len(block)) + 1):
            for subset in combinations(block, size):
                checked += 1
                if checked > policy.max_combinations_per_case:
                    exhausted = True
                    break
                if sum(bank.eligible_credit_minor for bank in subset) != order.expected_amount_minor:
                    continue
                candidates.append(
                    ProposedGroup(
                        (order.order_id,),
                        tuple(bank.bank_txn_id for bank in subset),
                        GroupType.ONE_ORDER_MANY_BANKS,
                        "L4",
                        MatchEvidence(
                            rule_id="L4_BOUNDED_SPLIT_CANDIDATE",
                            rule_version=policy.rule_version,
                            reason_codes=("EXACT_SUBSET_SUM", "IDENTITY_EVIDENCE_MISSING"),
                            explanation_vi=(
                                "Tổng nhiều bank rows bằng khoản phải thu nhưng thiếu mã tham chiếu; "
                                "chỉ đề xuất xác minh."
                            ),
                            amount_delta_minor=0,
                        ),
                        False,
                    )
                )
            if checked > policy.max_combinations_per_case:
                break
    return candidates, exhausted
