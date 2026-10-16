from dataclasses import replace
from pathlib import Path

from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.models import AllocationEdge
from smartrecon.domain.statuses import Currency
from smartrecon.engine import run_reconciliation
from smartrecon.evaluation.ground_truth import GroundTruth, load_ground_truth
from smartrecon.evaluation.metrics import evaluate_result
from smartrecon.ingest.mapping import default_demo_mapping
from smartrecon.ingest.normalization import normalize_bundle
from smartrecon.ingest.readers import read_source_bundle
from smartrecon.review import approve_group

DEMO_DIR = Path("data/demo/vn_synthetic_demo")


def _result():
    raw = read_source_bundle(
        orders_path=DEMO_DIR / "internal_receivables.csv",
        bank_path=DEMO_DIR / "bank_transactions.csv",
    )
    return run_reconciliation(
        normalize_bundle(raw, default_demo_mapping()),
        ReconciliationPolicy(currency=Currency.VND),
    )


def test_metrics_use_confirmed_edges_and_truth_is_split_without_overlap() -> None:
    truth = load_ground_truth(DEMO_DIR)
    development = truth.subset("development")
    holdout = truth.subset("holdout")
    result = _result()
    metrics = evaluate_result(result, truth)

    assert {edge.case_id for edge in development.edges}.isdisjoint({edge.case_id for edge in holdout.edges})
    assert {edge.case_id for edge in development.edges} | {edge.case_id for edge in holdout.edges} == {
        edge.case_id for edge in truth.edges
    }
    assert metrics.edge_precision.denominator == metrics.predicted_confirmed_edges
    assert metrics.edge_recall.denominator == metrics.truth_edges == len(truth.edges)
    assert metrics.candidate_recall.value is not None
    assert metrics.candidate_recall.value >= metrics.edge_recall.value
    assert metrics.allocation_total_absolute_error_minor > 0
    assert metrics.auto_confirmed_edges == metrics.predicted_confirmed_edges
    assert metrics.reviewed_confirmed_edges == 0


def test_reviewed_confirmation_is_not_counted_as_automatic_coverage() -> None:
    truth = load_ground_truth(DEMO_DIR)
    result = _result()
    proposal = next(group for group in result.groups if set(group.order_ids) == {"ORD00009", "ORD00010"})
    reviewed = evaluate_result(approve_group(result, proposal.group_id), truth)
    automatic = evaluate_result(result, truth)

    assert reviewed.edge_recall.numerator == automatic.edge_recall.numerator + 2
    assert reviewed.auto_confirm_coverage == automatic.auto_confirm_coverage
    assert reviewed.reviewed_confirmed_edges == 2


def test_false_edge_and_missing_edge_change_independent_counts() -> None:
    truth = load_ground_truth(DEMO_DIR)
    result = _result()
    baseline = evaluate_result(result, truth)
    removed = next(edge for edge in result.allocations if edge.order_id == "ORD00001")
    changed = replace(
        result,
        allocations=tuple(edge for edge in result.allocations if edge.edge_id != removed.edge_id)
        + (
            AllocationEdge(
                edge_id="evaluation-false-edge",
                group_id=removed.group_id,
                order_id="ORD00001",
                bank_txn_id="TXN00002",
                allocated_cash_minor=removed.allocated_cash_minor,
                currency=Currency.VND,
            ),
        ),
    )
    metrics = evaluate_result(changed, truth)
    assert metrics.false_auto_confirm_count >= 1
    assert metrics.edge_recall.numerator < metrics.edge_recall.denominator
    assert metrics.allocation_total_absolute_error_minor > baseline.allocation_total_absolute_error_minor


def test_zero_denominators_are_reported_as_not_applicable() -> None:
    empty = GroundTruth(edges=(), case_scenarios={}, manifest={})
    metrics = evaluate_result(_result(), empty)
    assert metrics.edge_precision.value is None
    assert metrics.edge_recall.value is None
    assert metrics.edge_f1 is None
