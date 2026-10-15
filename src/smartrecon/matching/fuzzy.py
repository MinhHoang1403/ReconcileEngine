"""RapidFuzz ranking behind strict blocks; scores are never probabilities."""

import re

from rapidfuzz import fuzz

from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.models import BankTransaction, MatchEvidence, Order
from smartrecon.domain.statuses import GroupType
from smartrecon.matching.models import ProposedGroup
from smartrecon.matching.references import fuzzy_text


def fuzzy_candidates(
    orders: list[Order], banks: list[BankTransaction], policy: ReconciliationPolicy
) -> list[ProposedGroup]:
    candidates: list[ProposedGroup] = []
    per_bank: dict[str, list[tuple[float, ProposedGroup]]] = {}
    for bank in banks:
        bank_texts = [fuzzy_text(value) for value in (bank.txn_ref, bank.description)]
        bank_texts = [value for value in bank_texts if value]
        bank_texts.extend(
            token for value in tuple(bank_texts) for token in re.findall(r"[\w-]{4,}", value) if token not in bank_texts
        )
        if not bank_texts:
            continue
        ranked: list[tuple[float, ProposedGroup]] = []
        for order in orders:
            if order.currency is not bank.currency or order.currency is not policy.currency:
                continue
            gap = ((bank.value_date or bank.txn_date) - order.ordered_at).days
            if not 0 <= gap <= policy.max_days_diff:
                continue
            if bank.eligible_credit_minor <= 0:
                continue
            amount_delta = abs(order.expected_amount_minor - bank.eligible_credit_minor)
            if amount_delta > max(order.expected_amount_minor // 10, 1):
                continue
            order_texts = [fuzzy_text(value) for value in (order.order_id, order.external_ref)]
            order_texts = [value for value in order_texts if value]
            if not order_texts:
                continue
            score = max(fuzz.WRatio(bank_text, order_text) for bank_text in bank_texts for order_text in order_texts)
            if score < policy.fuzzy_candidate_threshold:
                continue
            proposal = ProposedGroup(
                (order.order_id,),
                (bank.bank_txn_id,),
                GroupType.ONE_TO_ONE,
                "L3",
                MatchEvidence(
                    rule_id="L3_FUZZY_REFERENCE_CANDIDATE",
                    rule_version=policy.rule_version,
                    reason_codes=("FUZZY_REFERENCE", "REVIEW_REQUIRED"),
                    explanation_vi=("Chuỗi tham chiếu gần giống nhưng điểm fuzzy chỉ dùng xếp hạng; cần xác minh."),
                    amount_delta_minor=amount_delta,
                    date_delta_days=gap,
                    score=round(float(score), 4),
                    features={"score_semantics": "heuristic_ranking_not_probability"},
                ),
                False,
            )
            ranked.append((float(score), proposal))
        per_bank[bank.bank_txn_id] = sorted(ranked, key=lambda item: (-item[0], item[1].order_ids))[
            : policy.max_candidates_per_item
        ]
    for ranked in per_bank.values():
        candidates.extend(proposal for _, proposal in ranked)
    return candidates
