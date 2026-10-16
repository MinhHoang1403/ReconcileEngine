"""Run reproducible evaluation and a synthetic hard-profile benchmark."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import tempfile
import time
import tracemalloc
from dataclasses import asdict
from pathlib import Path
from typing import Any

from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.statuses import Currency
from smartrecon.engine import run_reconciliation
from smartrecon.evaluation.experiments import ablation_results
from smartrecon.evaluation.ground_truth import load_ground_truth
from smartrecon.evaluation.metrics import evaluate_result
from smartrecon.generation.synthetic import generate_vnd_demo, write_demo_bundle
from smartrecon.ingest.mapping import default_demo_mapping
from smartrecon.ingest.normalization import normalize_bundle
from smartrecon.ingest.readers import read_source_bundle
from smartrecon.review import approve_group

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "data" / "demo" / "vn_synthetic_demo"


def run_dataset(directory: Path):
    raw = read_source_bundle(
        orders_path=directory / "internal_receivables.csv",
        bank_path=directory / "bank_transactions.csv",
    )
    return run_reconciliation(
        normalize_bundle(raw, default_demo_mapping()),
        ReconciliationPolicy(currency=Currency.VND),
    )


def _commit() -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def evaluate(order_count: int, seed: int) -> dict[str, Any]:
    result = run_dataset(DEMO_DIR)
    truth = load_ground_truth(DEMO_DIR)
    holdout = truth.subset("holdout")
    review_group = next(
        group
        for group in result.groups
        if set(group.order_ids) == {"ORD00009", "ORD00010"} and set(group.bank_txn_ids) == {"TXN00007"}
    )
    reviewed_result = approve_group(result, review_group.group_id)

    with tempfile.TemporaryDirectory(prefix="smartrecon-evaluation-") as temporary:
        hard_dir = Path(temporary)
        bundle = generate_vnd_demo(
            seed=seed,
            order_count=order_count,
            profile="evaluation_hard",
        )
        write_demo_bundle(bundle, hard_dir)
        tracemalloc.start()
        started = time.perf_counter()
        hard_result = run_dataset(hard_dir)
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        hard_truth = load_ground_truth(hard_dir).subset("holdout")
        hard_metrics = evaluate_result(hard_result, hard_truth)

    return {
        "evaluation_protocol": {
            "truth_is_runtime_input": False,
            "split": "holdout",
            "split_rule": "sha256(case_id)[0] parity",
            "threshold_tuned_on_holdout": False,
        },
        "demo_manifest": truth.manifest,
        "holdout_metrics": evaluate_result(result, holdout).as_dict(),
        "decision_modes": {
            "engine_confirmed": evaluate_result(result, truth).as_dict(),
            "user_reviewed_example": {
                "note": (
                    "One known proposed group was explicitly approved to measure reviewed output; "
                    "it is not auto-confirm coverage."
                ),
                "metrics": evaluate_result(reviewed_result, truth).as_dict(),
            },
        },
        "ablation": ablation_results(result, holdout),
        "benchmark": {
            "profile": "seeded synthetic VND with hard cases and exact fillers",
            "seed": seed,
            "orders": order_count,
            "bank_transactions": len(hard_result.bank_transactions),
            "elapsed_seconds": elapsed,
            "peak_tracemalloc_bytes": peak,
            "dataset_hashes": bundle.manifest["semantic_hashes"],
            "policy": asdict(ReconciliationPolicy(currency=Currency.VND)),
            "metrics": hard_metrics.as_dict(),
            "hardware": {
                "platform": platform.platform(),
                "processor": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
                "python": platform.python_version(),
            },
            "commit": _commit(),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", type=int, default=1_000)
    parser.add_argument("--seed", type=int, default=20261016)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = evaluate(args.orders, args.seed)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
