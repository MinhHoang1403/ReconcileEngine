"""Benchmark representative reconciliation scenarios without a second engine."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import tempfile
import time
import tracemalloc
from dataclasses import asdict
from pathlib import Path
from statistics import mean
from typing import Any

from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.statuses import Currency
from smartrecon.engine import run_reconciliation
from smartrecon.ingest.mapping import default_demo_mapping
from smartrecon.ingest.normalization import normalize_bundle
from smartrecon.ingest.readers import read_source_bundle

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "demo" / "vn_synthetic_demo"
SCENARIOS = {
    "strong_reference": ("F01", "F02", "F03"),
    "weak_ambiguous": ("F04", "F05"),
    "many_orders_one_bank": ("F06",),
    "one_order_many_banks": ("F08",),
    "subset_search": ("F07",),
    "competing_proposals": ("F05", "F07", "F24"),
}


def _rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _selected_ids(case_ids: tuple[str, ...]) -> tuple[set[str], set[str]]:
    _, cases = _rows(DATA_DIR / "truth_cases.csv")
    selected = [row for row in cases if row["case_id"] in case_ids]
    orders = {value for row in selected for value in json.loads(row["order_ids"])}
    banks = {value for row in selected for value in json.loads(row["bank_txn_ids"])}
    return orders, banks


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _dataset(case_ids: tuple[str, ...], directory: Path) -> dict[str, Any]:
    order_ids, bank_ids = _selected_ids(case_ids)
    order_columns, all_orders = _rows(DATA_DIR / "internal_receivables.csv")
    bank_columns, all_banks = _rows(DATA_DIR / "bank_transactions.csv")
    orders = [row for row in all_orders if row["order_id"] in order_ids]
    banks = [row for row in all_banks if row["bank_txn_id"] in bank_ids]
    _write_csv(directory / "internal_receivables.csv", order_columns, orders)
    _write_csv(directory / "bank_transactions.csv", bank_columns, banks)
    digest = hashlib.sha256(
        json.dumps({"orders": orders, "banks": banks}, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {"orders": len(orders), "bank_transactions": len(banks), "semantic_hash": digest}


def _run(directory: Path):
    raw = read_source_bundle(
        orders_path=directory / "internal_receivables.csv",
        bank_path=directory / "bank_transactions.csv",
    )
    normalized = normalize_bundle(raw, default_demo_mapping())
    return run_reconciliation(normalized, ReconciliationPolicy(currency=Currency.VND))


def _commit() -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def benchmark(repeats: int) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="smartrecon-qa-benchmark-") as temporary:
        root = Path(temporary)
        for name, case_ids in SCENARIOS.items():
            directory = root / name
            directory.mkdir()
            metadata = _dataset(case_ids, directory)
            durations: list[float] = []
            peak_bytes = 0
            last_result = None
            for _ in range(repeats):
                tracemalloc.start()
                started = time.perf_counter()
                current = _run(directory)
                durations.append(time.perf_counter() - started)
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                peak_bytes = max(peak_bytes, peak)
                if last_result is not None:
                    assert current.semantic_checksum == last_result.semantic_checksum
                last_result = current
            ordered = sorted(durations)
            assert last_result is not None and last_result.conservation.is_valid
            results.append(
                {
                    "scenario": name,
                    "case_ids": list(case_ids),
                    **metadata,
                    "repeats": repeats,
                    "mean_seconds": mean(durations),
                    "p95_seconds": ordered[max(0, int(len(ordered) * 0.95) - 1)],
                    "peak_tracemalloc_bytes": peak_bytes,
                    "groups": len(last_result.groups),
                    "confirmed_edges": len(last_result.allocations),
                    "candidates": len(last_result.candidates),
                }
            )
    policy = ReconciliationPolicy(currency=Currency.VND)
    return {
        "seed": 42,
        "policy": asdict(policy),
        "commit": _commit(),
        "hardware": {
            "platform": platform.platform(),
            "processor": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
            "python": platform.python_version(),
        },
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=25)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeats < 1:
        raise ValueError("repeats must be positive")
    payload = benchmark(args.repeats)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
