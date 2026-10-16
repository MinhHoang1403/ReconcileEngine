"""Reproducible offline experiment projections over public engine output."""

from __future__ import annotations

from typing import Any

from smartrecon.engine import ReconciliationResult
from smartrecon.evaluation.ground_truth import GroundTruth
from smartrecon.evaluation.metrics import evaluate_result

ABLATION_VARIANTS = (
    ("Exact-reference baseline", {"L1"}),
    ("Reference + constrained", {"L1", "L2"}),
    ("Add fuzzy candidates", {"L1", "L2", "L3"}),
    ("Add bounded group/split candidates", {"L1", "L2", "L3", "L4"}),
    ("Full waterfall", None),
)


def ablation_results(result: ReconciliationResult, truth: GroundTruth) -> list[dict[str, Any]]:
    """Measure safe confirmation and retrieval at each public rule-layer prefix."""
    rows = []
    for name, layers in ABLATION_VARIANTS:
        metrics = evaluate_result(result, truth, allowed_layers=layers)
        rows.append(
            {
                "variant": name,
                "layers": sorted(layers) if layers else ["L1", "L2", "L3", "L4", "resolver", "allocation"],
                "edge_precision": metrics.edge_precision.value,
                "edge_recall": metrics.edge_recall.value,
                "edge_f1": metrics.edge_f1,
                "auto_confirm_coverage": metrics.auto_confirm_coverage.value,
                "false_auto_confirm_count": metrics.false_auto_confirm_count,
                "candidate_precision": metrics.candidate_precision.value,
                "candidate_recall": metrics.candidate_recall.value,
            }
        )
    return rows
