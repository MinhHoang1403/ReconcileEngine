"""Inspect supplied external synthetic schemas without inventing cash semantics or truth."""

import argparse
import hashlib
import inspect
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path


def evaluate(directory: Path) -> dict:
    from smartrecon.ingest.mapping import BANK_FIELDS, BANK_REQUIRED, ORDER_FIELDS, ORDER_REQUIRED, analyze_mapping
    from smartrecon.ingest.profiles import recognize_profiles
    from smartrecon.ingest.readers import read_source_bundle

    initial_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.glob("*.csv"))}
    pairs = []
    for file in ("oms_orders.csv", "shopee_settlement.csv", "tiktok_settlement.csv"):
        raw = read_source_bundle(orders_path=directory / file, bank_path=directory / "bank_statement.csv")
        orders = analyze_mapping(raw.orders.frame, ORDER_FIELDS, feed="orders", required_fields=ORDER_REQUIRED)
        banks = analyze_mapping(
            raw.bank_transactions.frame, BANK_FIELDS, feed="bank_transactions", required_fields=BANK_REQUIRED
        )
        profiles = recognize_profiles(raw)
        automatic = None
        try:
            from smartrecon.ingest.automation import plan_automatic_import
        except ModuleNotFoundError as error:
            if error.name != "smartrecon.ingest.automation":
                raise
            reasons = ["Automatic handoff not implemented in baseline"]
        else:
            plan = plan_automatic_import(
                raw, orders, banks, source_supported=all(p["status"] == "RECOGNIZED" for p in profiles.values())
            )
            automatic = asdict(plan.mapping) if plan.mapping else None
            reasons = plan.reasons
        pairs.append(
            {
                "receivable_file": file,
                "orders_rows": len(raw.orders.frame),
                "bank_rows": len(raw.bank_transactions.frame),
                "profiles": profiles,
                "mapping": {"orders": asdict(orders), "bank": asdict(banks)},
                "automatic_mapping": automatic,
                "automation_reasons": reasons,
                "financial_truth_available": False,
                "limitation": (
                    "Provided ground_truth has scenario/outcome labels, not allocated cash edges; "
                    "no financial metrics claimed"
                ),
            }
        )
    implementation = Path(inspect.getfile(analyze_mapping)).resolve()
    final_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.glob("*.csv"))}
    assert final_hashes == initial_hashes, "External inputs changed during inspection; do not compare this run"
    # Keep only schema/evidence reasons, never persist row samples from an external dataset.
    for pair in pairs:
        for analysis in pair["mapping"].values():
            for item in analysis["suggestions"]:
                item["sample_before"] = []
                item["sample_after"] = []
    return {
        "pairs": pairs,
        "source_commit": subprocess.check_output(
            ["git", "-C", str(implementation.parents[3]), "rev-parse", "HEAD"], text=True
        ).strip(),
        "mapping_source_sha256": hashlib.sha256(implementation.read_bytes()).hexdigest(),
        "input_hashes": final_hashes,
        "threshold_tuning": False,
        "external_files_modified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--core-source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.core_source:
        source = args.core_source.resolve()
        if not (source / "smartrecon/engine.py").is_file():
            parser.error("core-source must contain SmartRecon")
        sys.path.insert(0, str(source))
    result = evaluate(args.dataset.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps({"output": str(args.output), "rows": [(p["orders_rows"], p["bank_rows"]) for p in result["pairs"]]})
    )


if __name__ == "__main__":
    main()
