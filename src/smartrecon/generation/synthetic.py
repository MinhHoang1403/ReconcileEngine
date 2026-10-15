"""Seeded synthetic VND demo with evaluation truth stored in separate outputs."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openpyxl import Workbook

BUSINESS_TRUTH_DENYLIST = {
    "case_id",
    "ground_truth_case",
    "injected_scenario",
    "true_bank_id",
    "truth_group_id",
}

ORDER_COLUMNS = [
    "order_id",
    "ordered_at",
    "expected_amount",
    "currency",
    "order_status",
    "customer_name",
    "payment_channel",
    "external_ref",
    "description",
]
BANK_COLUMNS = [
    "bank_txn_id",
    "txn_ref",
    "txn_date",
    "value_date",
    "direction",
    "posted_amount",
    "currency",
    "amount_basis",
    "description",
    "sender_name",
    "channel",
    "batch_ref",
    "declared_fee",
]
TRUTH_EDGE_COLUMNS = [
    "case_id",
    "truth_group_id",
    "order_id",
    "bank_txn_id",
    "allocated_cash_minor",
    "currency",
    "truth_relation",
    "verified_adjustment_minor",
]
TRUTH_CASE_COLUMNS = [
    "case_id",
    "scenario",
    "order_ids",
    "bank_txn_ids",
    "expected_link_status",
    "expected_payment_status",
    "note",
]


@dataclass(frozen=True, slots=True)
class DemoBundle:
    """Business feeds plus isolated evaluation truth for one generated dataset."""

    orders: tuple[dict[str, Any], ...]
    bank_transactions: tuple[dict[str, Any], ...]
    truth_edges: tuple[dict[str, Any], ...]
    truth_cases: tuple[dict[str, Any], ...]
    manifest: dict[str, Any]


def _order(
    order_id: str,
    amount: int,
    day: int,
    *,
    external_ref: str | None = None,
    channel: str = "BANK_TRANSFER",
    description: str = "Khoản phải thu synthetic",
) -> dict[str, Any]:
    return {
        "order_id": order_id,
        "ordered_at": (date(2026, 1, 1) + timedelta(days=day)).isoformat(),
        "expected_amount": amount,
        "currency": "VND",
        "order_status": "ELIGIBLE",
        "customer_name": f"Khách {order_id[-4:]}",
        "payment_channel": channel,
        "external_ref": external_ref or order_id,
        "description": description,
    }


def _bank(
    bank_txn_id: str,
    amount: int,
    day: int,
    description: str,
    *,
    txn_ref: str | None = None,
    direction: str = "CREDIT",
    basis: str = "POSTED_CASH",
    channel: str = "BANK",
    declared_fee: int | None = None,
) -> dict[str, Any]:
    txn_date = date(2026, 1, 1) + timedelta(days=day)
    return {
        "bank_txn_id": bank_txn_id,
        "txn_ref": txn_ref or bank_txn_id,
        "txn_date": txn_date.isoformat(),
        "value_date": txn_date.isoformat(),
        "direction": direction,
        "posted_amount": amount,
        "currency": "VND",
        "amount_basis": basis,
        "description": description,
        "sender_name": "Người chuyển synthetic",
        "channel": channel,
        "batch_ref": "",
        "declared_fee": declared_fee if declared_fee is not None else "",
    }


def _edge(
    case_id: str,
    group_id: str,
    order_id: str,
    bank_txn_id: str,
    amount: int,
    relation: str,
    adjustment: int = 0,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "truth_group_id": group_id,
        "order_id": order_id,
        "bank_txn_id": bank_txn_id,
        "allocated_cash_minor": amount,
        "currency": "VND",
        "truth_relation": relation,
        "verified_adjustment_minor": adjustment,
    }


def _case(
    case_id: str,
    scenario: str,
    order_ids: list[str],
    bank_ids: list[str],
    link_status: str,
    payment_status: str,
    note: str,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "scenario": scenario,
        "order_ids": json.dumps(order_ids, ensure_ascii=False, separators=(",", ":")),
        "bank_txn_ids": json.dumps(bank_ids, ensure_ascii=False, separators=(",", ":")),
        "expected_link_status": link_status,
        "expected_payment_status": payment_status,
        "note": note,
    }


def _semantic_hash(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def generate_vnd_demo(seed: int = 42, order_count: int = 100) -> DemoBundle:
    """Generate 80–120 receivables with explicit hard cases and deterministic filler."""
    if not 80 <= order_count <= 120:
        raise ValueError("Demo phải có từ 80 đến 120 orders")
    rng = random.Random(seed)
    orders: list[dict[str, Any]] = []
    banks: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []

    def add_case(
        case_id: str,
        scenario: str,
        case_orders: list[dict[str, Any]],
        case_banks: list[dict[str, Any]],
        case_edges: list[dict[str, Any]],
        link: str,
        payment: str,
        note: str,
    ) -> None:
        orders.extend(case_orders)
        banks.extend(case_banks)
        edges.extend(case_edges)
        cases.append(
            _case(
                case_id,
                scenario,
                [row["order_id"] for row in case_orders],
                [row["bank_txn_id"] for row in case_banks],
                link,
                payment,
                note,
            )
        )

    add_case(
        "F01",
        "EXACT_REF",
        [_order("ORD00001", 300_000, 1)],
        [_bank("TXN00001", 300_000, 1, "Thanh toan ORD00001")],
        [_edge("F01", "TRUTH-F01", "ORD00001", "TXN00001", 300_000, "ONE_TO_ONE")],
        "CONFIRMED",
        "FULL",
        "Exact full token reference",
    )
    add_case(
        "F02",
        "TIMING_T_PLUS_N",
        [_order("ORD00002", 200_000, 2)],
        [_bank("TXN00002", 200_000, 4, "Thanh toan ORD00002")],
        [_edge("F02", "TRUTH-F02", "ORD00002", "TXN00002", 200_000, "ONE_TO_ONE")],
        "CONFIRMED",
        "FULL",
        "Full reference with T+2 lag",
    )
    add_case(
        "F03",
        "NORMALIZED_REF",
        [_order("ORD00003", 100_000, 3, external_ref="ORD-00003")],
        [_bank("TXN00003", 100_000, 3, "thanh toan ord 00003")],
        [_edge("F03", "TRUTH-F03", "ORD00003", "TXN00003", 100_000, "ONE_TO_ONE")],
        "CONFIRMED",
        "FULL",
        "Configured spacing/case normalization",
    )
    add_case(
        "F04",
        "FUZZY_OR_TYPO_REF",
        [_order("ORD00004", 100_000, 4)],
        [_bank("TXN00004", 100_000, 4, "Chuyen tien 0RD00004")],
        [_edge("F04", "TRUTH-F04", "ORD00004", "TXN00004", 100_000, "ONE_TO_ONE")],
        "PROPOSED",
        "UNKNOWN",
        "Typo is truth for evaluation but must not auto-confirm",
    )
    add_case(
        "F05",
        "AMBIGUOUS_CANDIDATES",
        [_order("ORD00005", 100_000, 5), _order("ORD00006", 100_000, 5)],
        [_bank("TXN00005", 100_000, 5, "Khach chuyen khoan")],
        [_edge("F05", "TRUTH-F05", "ORD00005", "TXN00005", 100_000, "ONE_TO_ONE")],
        "PROPOSED",
        "UNKNOWN",
        "Same amount/date has two candidates and no independent evidence",
    )
    add_case(
        "F06",
        "MANY_ORDERS_ONE_BANK",
        [_order("ORD00007", 300_000, 6), _order("ORD00008", 200_000, 6)],
        [_bank("TXN00006", 500_000, 6, "Thanh toan ORD00007 ORD00008")],
        [
            _edge("F06", "TRUTH-F06", "ORD00007", "TXN00006", 300_000, "MANY_ORDERS_ONE_BANK"),
            _edge("F06", "TRUTH-F06", "ORD00008", "TXN00006", 200_000, "MANY_ORDERS_ONE_BANK"),
        ],
        "CONFIRMED",
        "FULL",
        "Two full references and exact total",
    )
    add_case(
        "F07",
        "WEAK_MANY_ORDERS_ONE_BANK",
        [_order("ORD00009", 300_000, 7), _order("ORD00010", 200_000, 7)],
        [_bank("TXN00007", 500_000, 7, "Tong hop thanh toan")],
        [
            _edge("F07", "TRUTH-F07", "ORD00009", "TXN00007", 300_000, "MANY_ORDERS_ONE_BANK"),
            _edge("F07", "TRUTH-F07", "ORD00010", "TXN00007", 200_000, "MANY_ORDERS_ONE_BANK"),
        ],
        "PROPOSED",
        "UNKNOWN",
        "Exact subset without reference remains proposed",
    )
    add_case(
        "F08",
        "ONE_ORDER_MANY_BANKS",
        [_order("ORD00011", 600_000, 8)],
        [
            _bank("TXN00008", 200_000, 8, "Dot 1 ORD00011"),
            _bank("TXN00009", 400_000, 9, "Dot 2 ORD00011"),
        ],
        [
            _edge("F08", "TRUTH-F08", "ORD00011", "TXN00008", 200_000, "ONE_ORDER_MANY_BANKS"),
            _edge("F08", "TRUTH-F08", "ORD00011", "TXN00009", 400_000, "ONE_ORDER_MANY_BANKS"),
        ],
        "CONFIRMED",
        "FULL",
        "Two credits carry the same unique full reference",
    )
    add_case(
        "F09",
        "PARTIAL_UNDERPAY",
        [_order("ORD00012", 500_000, 9)],
        [_bank("TXN00010", 490_000, 9, "Thanh toan ORD00012")],
        [_edge("F09", "TRUTH-F09", "ORD00012", "TXN00010", 490_000, "ONE_TO_ONE")],
        "CONFIRMED",
        "PARTIAL",
        "Strong link with 10000 outstanding",
    )
    add_case(
        "F10",
        "OVERPAY",
        [_order("ORD00013", 500_000, 10)],
        [_bank("TXN00011", 520_000, 10, "Thanh toan ORD00013")],
        [_edge("F10", "TRUTH-F10", "ORD00013", "TXN00011", 500_000, "ONE_TO_ONE")],
        "CONFIRMED",
        "OVERPAID",
        "20000 remains unapplied on bank credit",
    )
    add_case(
        "F11",
        "ORPHAN_INTERNAL",
        [_order("ORD00014", 150_000, 11)],
        [],
        [],
        "UNMATCHED",
        "NO_CONFIRMED_RECEIPT",
        "No counterpart evidence generated",
    )
    add_case(
        "F12",
        "ORPHAN_BANK",
        [],
        [_bank("TXN00012", 85_000, 12, "Khong ro don hang")],
        [],
        "UNMATCHED",
        "UNKNOWN",
        "Eligible credit with no receivable counterpart",
    )
    duplicate_bank_a = _bank(
        "TXN00013-A", 120_000, 13, "Thanh toan ORD00015", txn_ref="BANK-STABLE-13"
    )
    duplicate_bank_b = dict(duplicate_bank_a, bank_txn_id="TXN00013-B")
    add_case(
        "F13",
        "DUPLICATE_IMPORT",
        [_order("ORD00015", 120_000, 13)],
        [duplicate_bank_a, duplicate_bank_b],
        [_edge("F13", "TRUTH-F13", "ORD00015", "TXN00013-A", 120_000, "ONE_TO_ONE")],
        "CONFIRMED",
        "FULL",
        "Second identical stable transaction is a re-import suspicion",
    )
    add_case(
        "F14",
        "DISTINCT_SAME_AMOUNT",
        [_order("ORD00016", 120_000, 14), _order("ORD00017", 120_000, 14)],
        [
            _bank("TXN00014", 120_000, 14, "Thanh toan ORD00016"),
            _bank("TXN00015", 120_000, 14, "Thanh toan ORD00017"),
        ],
        [
            _edge("F14", "TRUTH-F14-A", "ORD00016", "TXN00014", 120_000, "ONE_TO_ONE"),
            _edge("F14", "TRUTH-F14-B", "ORD00017", "TXN00015", 120_000, "ONE_TO_ONE"),
        ],
        "CONFIRMED",
        "FULL",
        "Distinct bank identities remain distinct",
    )
    add_case(
        "F15",
        "VERIFIED_PSP_FEE",
        [_order("ORD00018", 100_000, 15, channel="PSP")],
        [
            _bank(
                "TXN00016",
                98_000,
                15,
                "Settlement ORD00018 fee 2000",
                basis="NET_SETTLEMENT",
                channel="PSP",
                declared_fee=2_000,
            )
        ],
        [_edge("F15", "TRUTH-F15", "ORD00018", "TXN00016", 98_000, "ONE_TO_ONE", 2_000)],
        "CONFIRMED",
        "FULL",
        "Fee is backed by declared PSP settlement evidence",
    )
    add_case(
        "F16",
        "UNVERIFIED_FEE",
        [_order("ORD00019", 100_000, 16)],
        [_bank("TXN00017", 98_000, 16, "Thanh toan ORD00019")],
        [_edge("F16", "TRUTH-F16", "ORD00019", "TXN00017", 98_000, "ONE_TO_ONE")],
        "CONFIRMED",
        "PARTIAL",
        "Bank transfer shortfall is not an automatic fee",
    )
    add_case(
        "F17",
        "DEBIT_EXCLUDED",
        [_order("ORD00020", 90_000, 17)],
        [_bank("TXN00018", 90_000, 17, "Hoan tien ORD00020", direction="DEBIT")],
        [],
        "UNMATCHED",
        "NO_CONFIRMED_RECEIPT",
        "Debit is excluded from incoming cash pool",
    )
    add_case(
        "F18",
        "REFERENCE_BOUNDARY",
        [
            _order("DH01", 90_000, 18, external_ref="DH01"),
            _order("DH010", 80_000, 18, external_ref="DH010"),
        ],
        [_bank("TXN00019", 90_000, 18, "Thanh toan DH01")],
        [_edge("F18", "TRUTH-F18", "DH01", "TXN00019", 90_000, "ONE_TO_ONE")],
        "CONFIRMED",
        "FULL",
        "Token boundary must not select DH010",
    )
    add_case(
        "F22",
        "LEADING_ZERO_ID",
        [_order("00017", 77_000, 19, external_ref="00017")],
        [_bank("TXN00022", 77_000, 19, "Thanh toan 00017")],
        [_edge("F22", "TRUTH-F22", "00017", "TXN00022", 77_000, "ONE_TO_ONE")],
        "CONFIRMED",
        "FULL",
        "String identity retains leading zeros",
    )
    add_case(
        "F23",
        "FORMULA_INJECTION_SOURCE",
        [_order("ORD00028", 88_000, 20, description='=HYPERLINK("https://invalid")')],
        [_bank("TXN00023", 88_000, 20, "Thanh toan ORD00028")],
        [_edge("F23", "TRUTH-F23", "ORD00028", "TXN00023", 88_000, "ONE_TO_ONE")],
        "CONFIRMED",
        "FULL",
        "User-origin text must be escaped only on export",
    )
    add_case(
        "F24",
        "COMPLEX_MANY_TO_MANY",
        [_order("ORD00029", 130_000, 21), _order("ORD00030", 170_000, 21)],
        [
            _bank("TXN00024", 150_000, 21, "ORD00029 ORD00030 dot 1"),
            _bank("TXN00025", 150_000, 22, "ORD00029 ORD00030 dot 2"),
        ],
        [
            _edge("F24", "TRUTH-F24", "ORD00029", "TXN00024", 130_000, "MANY_TO_MANY"),
            _edge("F24", "TRUTH-F24", "ORD00030", "TXN00024", 20_000, "MANY_TO_MANY"),
            _edge("F24", "TRUTH-F24", "ORD00030", "TXN00025", 150_000, "MANY_TO_MANY"),
        ],
        "PROPOSED",
        "UNKNOWN",
        "General many-to-many remains review-only",
    )

    next_index = 31
    while len(orders) < order_count:
        order_id = f"ORD{next_index:05d}"
        bank_id = f"TXN{next_index:05d}"
        amount = rng.randrange(5, 151) * 10_000
        day = rng.randrange(0, 55)
        orders.append(_order(order_id, amount, day))
        banks.append(_bank(bank_id, amount, day + rng.randrange(0, 3), f"Thanh toan {order_id}"))
        edges.append(
            _edge(
                f"DEMO-{next_index:05d}",
                f"TRUTH-DEMO-{next_index:05d}",
                order_id,
                bank_id,
                amount,
                "ONE_TO_ONE",
            )
        )
        cases.append(
            _case(
                f"DEMO-{next_index:05d}",
                "EXACT_REF",
                [order_id],
                [bank_id],
                "CONFIRMED",
                "FULL",
                "Seeded exact filler",
            )
        )
        next_index += 1

    manifest = {
        "dataset_id": f"vn-synthetic-demo-seed-{seed}",
        "profile": "vn_synthetic_demo",
        "generator_version": "0.1.0",
        "seed": seed,
        "currency": "VND",
        "timezone": "Asia/Ho_Chi_Minh",
        "rounding_policy": "HALF_UP",
        "truth_version": "2026-10-15",
        "source_semantics": {
            "orders": "synthetic receivables",
            "bank_transactions": "synthetic posted bank/PSP rows; not real statements",
        },
        "observed_vs_synthetic_columns": {"all_business_columns": "synthetic"},
        "counts": {
            "orders": len(orders),
            "bank_transactions": len(banks),
            "truth_edges": len(edges),
            "truth_cases": len(cases),
        },
        "scenario_realized_counts": _scenario_counts(cases),
        "semantic_hashes": {
            "orders": _semantic_hash(orders),
            "bank_transactions": _semantic_hash(banks),
            "truth_edges": _semantic_hash(edges),
            "truth_cases": _semantic_hash(cases),
        },
        "reproducibility": (
            "CSV and semantic payloads are deterministic for seed/config; "
            "XLSX is semantically equivalent."
        ),
    }
    _assert_truth_isolated(orders, banks)
    return DemoBundle(tuple(orders), tuple(banks), tuple(edges), tuple(cases), manifest)


def _scenario_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        scenario = str(case["scenario"])
        counts[scenario] = counts.get(scenario, 0) + 1
    return dict(sorted(counts.items()))


def _assert_truth_isolated(
    orders: list[dict[str, Any]], bank_transactions: list[dict[str, Any]]
) -> None:
    leaked = (set(orders[0]) if orders else set()) | (
        set(bank_transactions[0]) if bank_transactions else set()
    )
    forbidden = sorted(leaked & BUSINESS_TRUTH_DENYLIST)
    if forbidden:
        raise AssertionError(f"Truth fields leaked into business feeds: {forbidden}")


def _write_csv(path: Path, rows: tuple[dict[str, Any], ...], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _append_sheet(
    workbook: Workbook,
    title: str,
    rows: tuple[dict[str, Any], ...],
    columns: list[str],
) -> None:
    sheet = workbook.create_sheet(title)
    sheet.append(columns)
    for row in rows:
        sheet.append([row[column] for column in columns])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions


def write_demo_bundle(bundle: DemoBundle, output_dir: Path) -> dict[str, str]:
    """Write two business feeds, a two-sheet workbook, isolated truth, and manifest."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "orders": output_dir / "internal_receivables.csv",
        "bank": output_dir / "bank_transactions.csv",
        "workbook": output_dir / "sample_reconciliation.xlsx",
        "truth_edges": output_dir / "truth_edges.csv",
        "truth_cases": output_dir / "truth_cases.csv",
        "manifest": output_dir / "manifest.json",
    }
    _write_csv(paths["orders"], bundle.orders, ORDER_COLUMNS)
    _write_csv(paths["bank"], bundle.bank_transactions, BANK_COLUMNS)
    _write_csv(paths["truth_edges"], bundle.truth_edges, TRUTH_EDGE_COLUMNS)
    _write_csv(paths["truth_cases"], bundle.truth_cases, TRUTH_CASE_COLUMNS)

    workbook = Workbook()
    workbook.remove(workbook.active)
    _append_sheet(workbook, "Internal", bundle.orders, ORDER_COLUMNS)
    _append_sheet(workbook, "Bank", bundle.bank_transactions, BANK_COLUMNS)
    workbook.save(paths["workbook"])

    paths["manifest"].write_text(
        json.dumps(bundle.manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return {name: str(path) for name, path in paths.items()}
