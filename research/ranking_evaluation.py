"""Evaluate a local Splink ranking model separately from financial confirmation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import logging
import platform
import re
import statistics
import subprocess
import time
import tracemalloc
from pathlib import Path

import pandas as pd

from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.statuses import Currency
from smartrecon.evaluation.ground_truth import load_ground_truth
from smartrecon.ingest.mapping import default_demo_mapping
from smartrecon.ingest.normalization import normalize_bundle
from smartrecon.ingest.readers import read_source_bundle
from smartrecon.matching.fuzzy import fuzzy_candidates
from smartrecon.matching.references import compact_reference, fuzzy_text

ROOT = Path(__file__).resolve().parents[1]


def features(orders, banks, *, missing_attributes: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Derive comparable observations without receiving any labels/known correct pairs."""
    order_rows = [
        {
            "unique_id": row.order_id,
            "reference": compact_reference(row.external_ref or row.order_id),
            "name": fuzzy_text(row.customer_name) or None,
            "amount": row.expected_amount_minor,
            "day": row.ordered_at.toordinal(),
            "currency": row.currency.value,
        }
        for row in orders
    ]
    bank_rows = []
    for row in banks:
        # A single reference feature is a deliberate limitation of this 1:1 challenger.
        # Multiple tokens remain review-only in production; no candidate here allocates money.
        tokens = re.findall(r"[A-Za-z]+[ _-]*[0-9]+", row.description or row.txn_ref or "")
        bank_rows.append(
            {
                "unique_id": row.bank_txn_id,
                "reference": compact_reference(tokens[0]) if tokens else None,
                "name": fuzzy_text(row.sender_name) or None,
                "amount": row.eligible_credit_minor,
                "day": (row.value_date or row.txn_date).toordinal(),
                "currency": row.currency.value,
            }
        )
    left, right = pd.DataFrame(order_rows), pd.DataFrame(bank_rows)
    if missing_attributes:
        left["name"] = None
        right["name"] = None
    return left, right


def linker_for(left: pd.DataFrame, right: pd.DataFrame, settings):
    from splink import DuckDBAPI, Linker

    database = DuckDBAPI()
    tables = [
        database.register(left, dataset_display_name="a_orders"),
        database.register(right, dataset_display_name="b_bank"),
    ]
    return Linker(tables, settings, log_level=logging.WARNING)


def train(left: pd.DataFrame, right: pd.DataFrame, *, missing_attributes: bool = False) -> dict:
    import splink.comparison_library as cl
    from splink import SettingsCreator, block_on

    comparisons = [cl.LevenshteinAtThresholds("reference", [1, 2]), cl.ExactMatch("amount"), cl.ExactMatch("day")]
    if not missing_attributes:
        comparisons.append(cl.LevenshteinAtThresholds("name", [1, 2]))
    settings = SettingsCreator(
        link_type="link_only",
        comparisons=comparisons,
        # Same amount/date/currency blocking envelope as the RapidFuzz baseline.
        blocking_rules_to_generate_predictions=[
            "l.currency = r.currency AND r.day - l.day BETWEEN 0 AND 3 "
            "AND abs(r.amount-l.amount) <= greatest(floor(l.amount/10),1)"
        ],
        max_iterations=25,
    )
    linker = linker_for(left, right, settings)
    linker.training.estimate_u_using_random_sampling(max_pairs=100000, seed=42, min_count_per_level=1)
    # Both are unsupervised EM blocks, not truth-labelled training pairs.
    linker.training.estimate_parameters_using_expectation_maximisation(block_on("reference"))
    linker.training.estimate_parameters_using_expectation_maximisation(block_on("amount"))
    return linker.misc.save_model_to_json()


def predict(left: pd.DataFrame, right: pd.DataFrame, model: dict) -> dict[str, list[str]]:
    linker = linker_for(left, right, model)
    pairs = linker.inference.predict(threshold_match_probability=0.0).as_pandas_dataframe()
    ranked = {}
    if not pairs.empty:
        assert set(pairs.unique_id_l) <= set(left.unique_id)
        assert set(pairs.unique_id_r) <= set(right.unique_id)
        pairs = pairs.sort_values(["unique_id_r", "match_weight", "unique_id_l"], ascending=[True, False, True])
        ranked = {
            str(bank_id): group.unique_id_l.astype(str).head(5).tolist()
            for bank_id, group in pairs.groupby("unique_id_r")
        }
    return ranked


def rapidfuzz_rank(orders, banks) -> dict[str, list[str]]:
    proposals = fuzzy_candidates(orders, banks, ReconciliationPolicy(Currency.VND))
    ranked = {}
    for bank in banks:
        choices = sorted(
            [item for item in proposals if item.bank_txn_ids == (bank.bank_txn_id,)],
            key=lambda item: (-(item.evidence.score or 0), item.order_ids),
        )
        ranked[bank.bank_txn_id] = [item.order_ids[0] for item in choices]
    return ranked


def metrics(ranked: dict[str, list[str]], truth) -> dict:
    expected = {(edge.order_id, edge.bank_txn_id) for edge in truth.edges}
    predicted = {(order_id, bank_id) for bank_id, choices in ranked.items() for order_id in choices}
    truth_banks = {bank for _, bank in expected}
    precision_at, reciprocal = {}, []
    for k in (1, 5):
        precision_at[str(k)] = statistics.mean(
            sum((order, bank) in expected for order in ranked.get(bank, [])[:k]) / k for bank in truth_banks
        )
    for bank in truth_banks:
        ranks = [index for index, order in enumerate(ranked.get(bank, []), start=1) if (order, bank) in expected]
        reciprocal.append(1 / min(ranks) if ranks else 0)
    return {
        "candidate_recall": len(predicted & expected) / len(expected),
        "precision_at_k": precision_at,
        "mrr": statistics.mean(reciprocal),
        "false_candidates": len(predicted - expected),
        "candidate_count": len(predicted),
        "truth_edges": len(expected),
        "mean_candidates_per_query": statistics.mean(len(ranked.get(bank, [])) for bank in truth_banks),
        "per_relation": {
            relation: {
                "truth_edges": len(keys),
                "candidate_recall": len(predicted & keys) / len(keys),
            }
            for relation in sorted({edge.relation for edge in truth.edges})
            if (keys := {(edge.order_id, edge.bank_txn_id) for edge in truth.edges if edge.relation == relation})
        },
    }


def evaluate(directory: Path, repeats: int) -> dict:
    raw = read_source_bundle(
        orders_path=directory / "internal_receivables.csv", bank_path=directory / "bank_transactions.csv"
    )
    inputs = normalize_bundle(raw, default_demo_mapping())
    orders = list(inputs.orders)
    banks = [
        row
        for row in inputs.bank_transactions
        if row.eligible_credit_minor > 0 and row.bank_txn_id not in inputs.duplicate_bank_ids
    ]
    truth = load_ground_truth(directory)
    development, holdout = truth.subset("development"), truth.subset("holdout")
    train_orders = {edge.order_id for edge in development.edges}
    train_banks = {edge.bank_txn_id for edge in development.edges}
    test_orders = {edge.order_id for edge in holdout.edges}
    test_banks = {edge.bank_txn_id for edge in holdout.edges}
    # Do not train on participants shared across splits, even when cases are malformed.
    if train_orders & test_orders or train_banks & test_banks:
        raise ValueError("Development and holdout must not share participants")
    dev_orders = [row for row in orders if row.order_id in train_orders]
    dev_banks = [row for row in banks if row.bank_txn_id in train_banks]
    eval_banks = [row for row in banks if row.bank_txn_id in test_banks]
    methods = {"rapidfuzz": lambda: rapidfuzz_rank(orders, eval_banks)}
    models, training_times = {}, {}
    for missing in (False, True):
        name = "splink_without_name" if missing else "splink"
        started = time.perf_counter()
        model = train(*features(dev_orders, dev_banks, missing_attributes=missing), missing_attributes=missing)
        training_times[name] = time.perf_counter() - started
        models[name] = model
        left, right = features(orders, eval_banks, missing_attributes=missing)
        methods[name] = lambda left=left, right=right, model=model: predict(left, right, model)
    results = {}
    for name, method in methods.items():
        method()
        seconds, peaks = [], []
        for _ in range(repeats):
            tracemalloc.start()
            started = time.perf_counter()
            ranked = method()
            seconds.append(time.perf_counter() - started)
            peaks.append(tracemalloc.get_traced_memory()[1])
            tracemalloc.stop()
        if name == "rapidfuzz":
            reversed_result = rapidfuzz_rank(orders[::-1], eval_banks[::-1])
        else:
            left, right = features(orders[::-1], eval_banks[::-1], missing_attributes=name == "splink_without_name")
            reversed_result = predict(left, right, models[name])
        results[name] = {
            **metrics(ranked, holdout),
            "rankings": ranked,
            "order_invariant": ranked == reversed_result,
            "median_seconds": statistics.median(seconds),
            "seconds": seconds,
            "peak_python_bytes": max(peaks),
        }
    return {
        "seed": 42,
        "repeats": repeats,
        "split": "existing_case_hash_holdout",
        "splink": importlib.metadata.version("splink"),
        "model_calibrated": False,
        "training_seconds": training_times,
        "models": models,
        "methods": results,
        "input_hashes": {
            key: hashlib.sha256((directory / filename).read_bytes()).hexdigest()
            for key, filename in (("orders", "internal_receivables.csv"), ("bank", "bank_transactions.csv"))
        },
        "runtime_auto_confirm_policy_changed": False,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "libraries": {name: importlib.metadata.version(name) for name in ("pandas", "rapidfuzz", "duckdb")},
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/demo/vn_synthetic_demo")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    result = evaluate(args.dataset.resolve(), args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "methods": {
                    name: {key: value for key, value in row.items() if key != "rankings"}
                    for name, row in result["methods"].items()
                },
            }
        )
    )


if __name__ == "__main__":
    main()
