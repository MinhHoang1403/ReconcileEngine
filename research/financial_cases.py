"""Independent, seeded grouped-payment holdout; imports no SmartRecon runtime code."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from pathlib import Path


def write_holdout(directory: Path, *, seed: int = 20261020, cases_per_relation: int = 40) -> dict:
    """Declare cash flows before execution; never use a matcher to manufacture labels."""
    rng = random.Random(seed)
    orders, banks, edges, cases = [], [], [], []

    def order(identifier: str, amount: int, reference: str = "") -> None:
        orders.append(
            {
                "order_id": identifier,
                "ordered_at": "2026-10-19",
                "expected_amount": amount,
                "currency": "VND",
                "order_status": "ELIGIBLE",
                "customer_name": "",
                "payment_channel": "BANK_TRANSFER",
                "external_ref": reference,
                "description": "",
            }
        )

    def bank(identifier: str, amount: int, memo: str) -> None:
        banks.append(
            {
                "bank_txn_id": identifier,
                "txn_ref": identifier,
                "txn_date": "2026-10-20",
                "value_date": "2026-10-20",
                "direction": "CREDIT",
                "posted_amount": amount,
                "currency": "VND",
                "amount_basis": "POSTED_CASH",
                "description": memo,
                "sender_name": "",
                "channel": "BANK_TRANSFER",
                "batch_ref": "",
                "declared_fee": "",
            }
        )

    def edge(case: str, order_id: str, bank_id: str, amount: int, relation: str) -> None:
        edges.append(
            {
                "case_id": case,
                "truth_group_id": case,
                "order_id": order_id,
                "bank_txn_id": bank_id,
                "allocated_cash_minor": amount,
                "truth_relation": relation,
            }
        )

    for relation in ("1:1", "N:1", "1:N", "M:N"):
        for index in range(cases_per_relation):
            case = f"H-{relation.replace(':', '')}-{index:04}"
            cases.append({"case_id": case, "scenario": relation})
            a, b, c = (rng.randint(10001, 999999) for _ in range(3))
            first, second = f"{case}-OA", f"{case}-OB"
            pay_a, pay_b = f"{case}-BA", f"{case}-BB"
            if relation == "1:1":
                order(first, a)
                bank(pay_a, a, first)
                edge(case, first, pay_a, a, relation)
            elif relation == "N:1":
                order(first, a)
                order(second, b)
                bank(pay_a, a + b, f"{first} {second}")
                edge(case, first, pay_a, a, relation)
                edge(case, second, pay_a, b, relation)
            elif relation == "1:N":
                order(first, a + b)
                bank(pay_a, a, first)
                bank(pay_b, b, first)
                edge(case, first, pay_a, a, relation)
                edge(case, first, pay_b, b, relation)
            else:
                order(first, a + b)
                order(second, c)
                bank(pay_a, a, first)
                bank(pay_b, b + c, f"{first} {second}")
                edge(case, first, pay_a, a, relation)
                edge(case, first, pay_b, b, relation)
                edge(case, second, pay_b, c, relation)

    for index in range(10):
        case = f"H-COLLISION-{index:04}"
        cases.append({"case_id": case, "scenario": "conflicting_reference"})
        a = rng.randint(10001, 999999)
        first, second, payment, shared = (f"{case}-{suffix}" for suffix in ("OA", "OB", "BA", "SHARED"))
        order(first, a, shared)
        order(second, a, shared)
        bank(payment, a, f"{first} {shared}")
        edge(case, second, payment, a, "1:1")

        case = f"H-UNICODE-{index:04}"
        cases.append({"case_id": case, "scenario": "unicode_prefix_is_not_reference"})
        identifier = f"DH{index:06}"
        order(identifier, a)
        bank(f"{case}-BA", a, f"Đ{identifier}")
        # No truth edge: unrelated bank credit. Global false-auto audit includes zero-edge cases.

    rng.shuffle(orders)
    rng.shuffle(banks)
    directory.mkdir(parents=True, exist_ok=True)
    for name, rows in (
        ("internal_receivables.csv", orders),
        ("bank_transactions.csv", banks),
        ("truth_edges.csv", edges),
        ("truth_cases.csv", cases),
    ):
        with (directory / name).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    manifest = {
        "generator": "independent_financial_cases",
        "seed": seed,
        "cases_per_relation": cases_per_relation,
        "orders": len(orders),
        "banks": len(banks),
        "truth_edges": len(edges),
        "cases": len(cases),
        "currency": "VND",
        "used_for_threshold_tuning": False,
        "semantic_hashes": {
            name: hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
            for name, rows in (("orders", orders), ("banks", banks), ("truth", edges))
        },
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
