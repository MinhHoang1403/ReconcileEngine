"""Compare schema methods against independent answers without exposing truth to any matcher."""

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
import time
import tracemalloc
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd
from mapping_cases import MappingCase, mapping_cases


def contract(case: MappingCase) -> tuple[set[str], set[str]]:
    from smartrecon.ingest.mapping import BANK_FIELDS, BANK_REQUIRED, ORDER_FIELDS, ORDER_REQUIRED

    return (ORDER_FIELDS, ORDER_REQUIRED) if case.feed == "orders" else (BANK_FIELDS, BANK_REQUIRED)


def current(case: MappingCase) -> dict[str, str]:
    from smartrecon.ingest.mapping import analyze_mapping

    targets, required = contract(case)
    return analyze_mapping(
        case.frame,
        targets,
        feed=case.feed,
        required_fields=required,
        profile_mapping=case.profile,
    ).selected_mapping


def coma(case: MappingCase) -> dict[str, str]:
    from valentine import valentine_match
    from valentine.algorithms import Coma

    targets = sorted(contract(case)[0])
    # Reference schema is fixed by the product contract; source values/labels are independent.
    examples = {
        "order_id": ["ORD101", "ORD102"],
        "bank_txn_id": ["TX101", "TX102"],
        "ordered_at": ["2026-10-18", "2026-10-19"],
        "txn_date": ["2026-10-18", "2026-10-19"],
        "expected_amount": ["450000", "780000"],
        "posted_amount": ["450000", "780000"],
        "declared_fee": ["2000", "4000"],
        "currency": ["VND", "VND"],
        "direction": ["CREDIT", "DEBIT"],
        "amount_basis": ["POSTED_CASH", "NET_SETTLEMENT"],
    }
    reference = pd.DataFrame({target: examples.get(target, ["text", "text"]) for target in targets})
    result = valentine_match([case.frame, reference], Coma(max_n=0, use_instances=True))
    chosen = result.one_to_one_hungarian()
    return {pair.target_column: pair.source_column for pair in chosen}


def hybrid(case: MappingCase) -> dict[str, str]:
    primary, secondary = current(case), coma(case)
    return {target: source for target, source in primary.items() if secondary.get(target) == source}


def evaluate(method: str, repeats: int) -> dict[str, Any]:
    from smartrecon.ingest.mapping import analyze_mapping

    matcher = {"current": current, "coma": coma, "hybrid": hybrid}[method]
    cases = mapping_cases()
    measurements = []
    rows = []
    for case in cases:
        matcher(case)  # warmup; do not mix import/JIT cost with repeated timings
        seconds = []
        peaks = []
        for _ in range(repeats):
            tracemalloc.start()
            started = time.perf_counter()
            predicted = matcher(case)
            seconds.append(time.perf_counter() - started)
            peaks.append(tracemalloc.get_traced_memory()[1])
            tracemalloc.stop()
        truth = set(case.expected.items())
        prediction = set(predicted.items())
        correct = len(truth & prediction)
        rows.append(
            {
                "case": case.name,
                "split": case.split,
                "expected": case.expected,
                "abstain": case.abstain,
                "predicted": predicted,
                "correct": correct,
                "wrong": len(prediction - truth),
                "missed": len(truth - prediction),
                "required_decisions": len(truth) + len(case.abstain),
                "manual_decisions": len(truth - prediction) + len(case.abstain),
                "median_seconds": statistics.median(seconds),
                "peak_python_bytes": max(peaks),
            }
        )
        measurements.extend(seconds)
    totals = {
        "correct": sum(row["correct"] for row in rows),
        "wrong": sum(row["wrong"] for row in rows),
        "missed": sum(row["missed"] for row in rows),
        "manual_decisions": sum(row["manual_decisions"] for row in rows),
        "median_case_seconds": statistics.median(measurements),
    }
    totals["precision"] = (
        totals["correct"] / (totals["correct"] + totals["wrong"]) if totals["correct"] + totals["wrong"] else None
    )
    totals["recall"] = (
        totals["correct"] / (totals["correct"] + totals["missed"]) if totals["correct"] + totals["missed"] else None
    )
    totals["auto_mapping_coverage"] = (totals["correct"] + totals["wrong"]) / sum(
        row["required_decisions"] for row in rows
    )
    implementation = Path(inspect.getfile(analyze_mapping))
    source_root = implementation.resolve().parents[3]
    return {
        "method": method,
        "repeats": repeats,
        "protocol": "full_business_contract_without_truth_in_matcher",
        "case_hash": hashlib.sha256(json.dumps([asdict(case) for case in cases], sort_keys=True).encode()).hexdigest(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "implementation_file": str(implementation),
        "implementation_sha256": hashlib.sha256(implementation.read_bytes()).hexdigest(),
        "implementation_commit": subprocess.check_output(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"], text=True
        ).strip(),
        "implementation_modified": bool(
            subprocess.check_output(
                ["git", "-C", str(source_root), "status", "--porcelain", "--", str(implementation)], text=True
            ).strip()
        ),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "pandas": pd.__version__,
            "valentine": importlib.metadata.version("valentine") if method in {"coma", "hybrid"} else None,
        },
        "summary": totals,
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", choices=["current", "coma", "hybrid"], default="current")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--core-source", type=Path, help="Read an explicit baseline src directory without modifying it")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    if args.core_source:
        source = args.core_source.resolve()
        if not (source / "smartrecon" / "ingest" / "mapping.py").is_file():
            parser.error("core-source must contain smartrecon/ingest/mapping.py")
        sys.path.insert(0, str(source))
    result = evaluate(args.method, args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
