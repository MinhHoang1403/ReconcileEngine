"""Run full-engine development sensitivity and repeated dataset evaluation without tuning holdout."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from dataclasses import asdict
from itertools import product
from pathlib import Path


def evaluate(directory: Path, repeats: int) -> dict:
    from smartrecon.config import ReconciliationPolicy
    from smartrecon.domain.statuses import Currency
    from smartrecon.engine import run_reconciliation
    from smartrecon.evaluation.ground_truth import load_ground_truth
    from smartrecon.evaluation.metrics import evaluate_result
    from smartrecon.generation.synthetic import generate_vnd_demo, write_demo_bundle
    from smartrecon.ingest.mapping import default_demo_mapping
    from smartrecon.ingest.normalization import normalize_bundle
    from smartrecon.ingest.readers import read_source_bundle

    def dataset(path: Path):
        raw = read_source_bundle(
            orders_path=path / "internal_receivables.csv", bank_path=path / "bank_transactions.csv"
        )
        return normalize_bundle(raw, default_demo_mapping())

    inputs = dataset(directory)
    truth = load_ground_truth(directory)
    default = ReconciliationPolicy(Currency.VND)
    sensitivity = []
    # Predeclared grid; report development only and retain the original policy.
    for gap, threshold, size in product((0, 1, 3, 7), (70, 85, 95), (2, 3, 4)):
        policy = ReconciliationPolicy(
            Currency.VND,
            max_days_diff=gap,
            fuzzy_candidate_threshold=threshold,
            max_group_orders=size,
            max_split_bank_rows=size,
        )
        result = run_reconciliation(inputs, policy)
        assert result.conservation.is_valid
        sensitivity.append(
            {
                "policy": asdict(policy),
                "metrics": evaluate_result(result, truth.subset("development")).as_dict(),
                "layer_counts": result.layer_counts,
            }
        )

    def measure(bundle, labels) -> dict:
        result = run_reconciliation(bundle, default)
        seconds, peaks = [], []
        for _ in range(repeats):
            tracemalloc.start()
            started = time.perf_counter()
            repeated = run_reconciliation(bundle, default)
            seconds.append(time.perf_counter() - started)
            peaks.append(tracemalloc.get_traced_memory()[1])
            tracemalloc.stop()
            assert repeated.semantic_checksum == result.semantic_checksum
            assert repeated.conservation.is_valid
        return {
            "metrics": evaluate_result(result, labels).as_dict(),
            "layer_counts": result.layer_counts,
            "median_seconds": statistics.median(seconds),
            "seconds": seconds,
            "peak_python_bytes": max(peaks),
            "semantic_checksum": result.semantic_checksum,
            "conservation": result.conservation.is_valid,
            "confirmed_cash_minor": result.kpis["confirmed_cash_allocated_minor"],
            "orders": len(result.orders),
            "banks": len(result.bank_transactions),
            "allocations": sorted(
                (edge.order_id, edge.bank_txn_id, edge.allocated_cash_minor) for edge in result.allocations
            ),
        }

    with tempfile.TemporaryDirectory(prefix="smartrecon-matching-research-") as temporary:
        hard_path = Path(temporary)
        hard = generate_vnd_demo(seed=20261016, order_count=1000, profile="evaluation_hard")
        write_demo_bundle(hard, hard_path)
        hard_result = measure(dataset(hard_path), load_ground_truth(hard_path))
        hard_result["dataset_hashes"] = hard.manifest["semantic_hashes"]
    core_path = Path(inspect.getfile(run_reconciliation)).resolve().parents[1]
    source_root = core_path.parent
    matching = core_path / "smartrecon" / "matching"
    return {
        "seed": 20261016,
        "repeats": repeats,
        "policy": asdict(default),
        "policy_changed": False,
        "threshold_tuned_on_holdout": False,
        "development_sensitivity": sensitivity,
        "demo": measure(inputs, truth),
        "holdout_metrics": evaluate_result(run_reconciliation(inputs, default), truth.subset("holdout")).as_dict(),
        "hard": hard_result,
        "source_commit": subprocess.check_output(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"], text=True
        ).strip(),
        "source_modified": bool(
            subprocess.check_output(
                ["git", "-C", str(source_root), "status", "--porcelain", "--", str(matching)], text=True
            ).strip()
        ),
        "matching_source_hashes": {
            file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in sorted(matching.glob("*.py"))
        },
        "dataset_hashes": {
            file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in sorted(directory.glob("*.csv"))
        },
        "environment": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "libraries": {name: importlib.metadata.version(name) for name in ("pandas", "rapidfuzz", "duckdb")},
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--core-source", type=Path)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    if args.core_source:
        source = args.core_source.resolve()
        if not (source / "smartrecon" / "engine.py").is_file():
            parser.error("core-source must contain smartrecon/engine.py")
        sys.path.insert(0, str(source))
    result = evaluate(args.dataset.resolve(), args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "demo_f1": result["demo"]["metrics"]["edge_f1"],
                "hard_f1": result["hard"]["metrics"]["edge_f1"],
                "policy_changed": False,
            }
        )
    )


if __name__ == "__main__":
    main()
