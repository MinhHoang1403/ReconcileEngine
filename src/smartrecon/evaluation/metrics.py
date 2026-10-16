"""Independent edge, group, allocation, and retrieval evaluation metrics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any

from smartrecon.engine import ReconciliationResult
from smartrecon.evaluation.ground_truth import GroundTruth, TruthEdge

EdgeKey = tuple[str, str]
GroupKey = tuple[frozenset[str], frozenset[str]]


@dataclass(frozen=True, slots=True)
class RateMetric:
    numerator: int
    denominator: int
    value: float | None


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    edge_precision: RateMetric
    edge_recall: RateMetric
    edge_f1: float | None
    group_precision: RateMetric
    group_recall: RateMetric
    candidate_precision: RateMetric
    candidate_recall: RateMetric
    auto_confirm_coverage: RateMetric
    false_auto_confirm_count: int
    false_auto_confirm_rate: RateMetric
    allocation_mae_minor: float | None
    allocation_total_absolute_error_minor: int
    per_relation: dict[str, dict[str, Any]]
    predicted_confirmed_edges: int
    auto_confirmed_edges: int
    reviewed_confirmed_edges: int
    retrieved_edges: int
    truth_edges: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rate(numerator: int, denominator: int) -> RateMetric:
    return RateMetric(numerator, denominator, numerator / denominator if denominator else None)


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or precision + recall == 0:
        return None
    return 2 * precision * recall / (precision + recall)


def evaluate_result(
    result: ReconciliationResult,
    truth: GroundTruth,
    *,
    allowed_layers: set[str] | None = None,
) -> EvaluationMetrics:
    """Evaluate confirmed cash separately from retrievable proposals.

    `allowed_layers` supports offline ablation by filtering public rule IDs. It
    does not change or reimplement matching behavior.
    """
    truth_by_key = {(edge.order_id, edge.bank_txn_id): edge for edge in truth.edges}
    truth_keys = set(truth_by_key)
    truth_orders = {edge.order_id for edge in truth.edges}
    truth_banks = {edge.bank_txn_id for edge in truth.edges}

    def allowed(rule_id: str) -> bool:
        return allowed_layers is None or rule_id.split("_", 1)[0] in allowed_layers

    groups_by_id = {group.group_id: group for group in result.groups}
    group_rules = {group.group_id: group.evidence.rule_id for group in result.groups}
    predicted_amounts = {
        (edge.order_id, edge.bank_txn_id): edge.allocated_cash_minor
        for edge in result.allocations
        if (edge.order_id in truth_orders or edge.bank_txn_id in truth_banks)
        and allowed(group_rules.get(edge.group_id, ""))
    }
    predicted_keys = set(predicted_amounts)
    auto_predicted_keys = {
        (edge.order_id, edge.bank_txn_id)
        for edge in result.allocations
        if (group := groups_by_id.get(edge.group_id)) is not None
        and group.review_status.value == "NOT_REQUIRED"
        and (edge.order_id in truth_orders or edge.bank_txn_id in truth_banks)
        and allowed(group.evidence.rule_id)
    }
    reviewed_predicted_keys = {
        (edge.order_id, edge.bank_txn_id)
        for edge in result.allocations
        if (group := groups_by_id.get(edge.group_id)) is not None
        and group.review_status.value == "APPROVED"
        and (edge.order_id in truth_orders or edge.bank_txn_id in truth_banks)
        and allowed(group.evidence.rule_id)
    }
    retrieved_keys = set(predicted_keys)
    for candidate in result.candidates:
        if not allowed(candidate.evidence.rule_id):
            continue
        retrieved_keys.update(
            (order_id, bank_id)
            for order_id in candidate.order_ids
            for bank_id in candidate.bank_txn_ids
            if order_id in truth_orders or bank_id in truth_banks
        )

    tp = len(predicted_keys & truth_keys)
    fp = len(predicted_keys - truth_keys)
    auto_tp = len(auto_predicted_keys & truth_keys)
    auto_fp = len(auto_predicted_keys - truth_keys)
    fn = len(truth_keys - predicted_keys)
    precision = _rate(tp, tp + fp)
    recall = _rate(tp, tp + fn)

    predicted_groups = {
        (frozenset(group.order_ids), frozenset(group.bank_txn_ids))
        for group in result.groups
        if group.link_status.value == "CONFIRMED"
        and allowed(group.evidence.rule_id)
        and (set(group.order_ids) & truth_orders or set(group.bank_txn_ids) & truth_banks)
    }
    truth_groups = _truth_groups(truth.edges)
    group_tp = len(predicted_groups & truth_groups)

    evaluated_keys = predicted_keys | truth_keys
    errors = [
        abs(predicted_amounts.get(key, 0) - (truth_by_key[key].allocated_cash_minor if key in truth_by_key else 0))
        for key in evaluated_keys
    ]
    per_relation = {
        relation: _relation_metrics(
            predicted_keys,
            retrieved_keys,
            tuple(edge for edge in truth.edges if edge.relation == relation),
        )
        for relation in sorted({edge.relation for edge in truth.edges})
    }
    return EvaluationMetrics(
        edge_precision=precision,
        edge_recall=recall,
        edge_f1=_f1(precision.value, recall.value),
        group_precision=_rate(group_tp, len(predicted_groups)),
        group_recall=_rate(group_tp, len(truth_groups)),
        candidate_precision=_rate(len(retrieved_keys & truth_keys), len(retrieved_keys)),
        candidate_recall=_rate(len(retrieved_keys & truth_keys), len(truth_keys)),
        auto_confirm_coverage=_rate(auto_tp, len(truth_keys)),
        false_auto_confirm_count=auto_fp,
        false_auto_confirm_rate=_rate(auto_fp, len(auto_predicted_keys)),
        allocation_mae_minor=mean(errors) if errors else None,
        allocation_total_absolute_error_minor=sum(errors),
        per_relation=per_relation,
        predicted_confirmed_edges=len(predicted_keys),
        auto_confirmed_edges=len(auto_predicted_keys),
        reviewed_confirmed_edges=len(reviewed_predicted_keys),
        retrieved_edges=len(retrieved_keys),
        truth_edges=len(truth_keys),
    )


def _truth_groups(edges: tuple[TruthEdge, ...]) -> set[GroupKey]:
    participants: dict[str, tuple[set[str], set[str]]] = {}
    for edge in edges:
        orders, banks = participants.setdefault(edge.truth_group_id, (set(), set()))
        orders.add(edge.order_id)
        banks.add(edge.bank_txn_id)
    return {(frozenset(orders), frozenset(banks)) for orders, banks in participants.values()}


def _relation_metrics(
    predicted: set[EdgeKey],
    retrieved: set[EdgeKey],
    edges: tuple[TruthEdge, ...],
) -> dict[str, Any]:
    truth = {(edge.order_id, edge.bank_txn_id) for edge in edges}
    orders = {edge.order_id for edge in edges}
    banks = {edge.bank_txn_id for edge in edges}
    scoped_predicted = {key for key in predicted if key[0] in orders or key[1] in banks}
    scoped_retrieved = {key for key in retrieved if key[0] in orders or key[1] in banks}
    confirmed_tp = len(scoped_predicted & truth)
    candidate_tp = len(scoped_retrieved & truth)
    return {
        "truth_edges": len(truth),
        "confirmed_precision": _rate(confirmed_tp, len(scoped_predicted)).value,
        "confirmed_recall": _rate(confirmed_tp, len(truth)).value,
        "candidate_precision": _rate(candidate_tp, len(scoped_retrieved)).value,
        "candidate_recall": _rate(candidate_tp, len(truth)).value,
    }
