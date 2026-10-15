"""Policy-constrained candidates; amount/date without identity never auto-confirms."""

from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.models import BankTransaction, MatchEvidence, Order
from smartrecon.domain.statuses import GroupType
from smartrecon.matching.models import ProposedGroup


def amount_date_candidates(
    orders: list[Order], banks: list[BankTransaction], policy: ReconciliationPolicy
) -> list[ProposedGroup]:
    candidates: list[ProposedGroup] = []
    for order in sorted(orders, key=lambda row: row.order_id):
        for bank in sorted(banks, key=lambda row: row.bank_txn_id):
            if order.currency is not bank.currency or order.currency is not policy.currency:
                continue
            gap = ((bank.value_date or bank.txn_date) - order.ordered_at).days
            if not 0 <= gap <= policy.max_days_diff:
                continue
            if order.expected_amount_minor != bank.eligible_credit_minor:
                continue
            candidates.append(
                ProposedGroup(
                    (order.order_id,),
                    (bank.bank_txn_id,),
                    GroupType.ONE_TO_ONE,
                    "L2",
                    MatchEvidence(
                        rule_id="L2_AMOUNT_DATE_CANDIDATE",
                        rule_version=policy.rule_version,
                        reason_codes=(
                            "AMOUNT_EXACT",
                            "DATE_IN_WINDOW",
                            "IDENTITY_EVIDENCE_MISSING",
                        ),
                        explanation_vi=("Số tiền và ngày phù hợp nhưng thiếu định danh độc lập; chỉ đề xuất xác minh."),
                        amount_delta_minor=0,
                        date_delta_days=gap,
                    ),
                    False,
                )
            )
    return candidates
