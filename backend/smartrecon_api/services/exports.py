"""Excel reporting from one persisted run snapshot with formula-injection protection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from backend.smartrecon_api.services.artifacts import run_directory


def safe_excel_value(value: Any) -> Any:
    """Force user-origin formula prefixes to remain text in spreadsheet clients."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _safe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        flattened: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, sort_keys=True)
            flattened[key] = safe_excel_value(value)
        result.append(flattened)
    return result


def create_excel_export(run_id: str, result: dict[str, Any], revision: int = 0) -> Path:
    """Generate a run/revision-scoped workbook; no Excel formula computes business values."""
    output = run_directory(run_id) / "exports" / f"reconciliation-r{revision}.xlsx"
    output.parent.mkdir(parents=True, exist_ok=True)
    order_allocated: dict[str, int] = {}
    bank_allocated: dict[str, int] = {}
    for edge in result["allocations"]:
        order_id = edge["order_id"]
        bank_id = edge["bank_txn_id"]
        order_allocated[order_id] = order_allocated.get(order_id, 0) + edge["allocated_cash_minor"]
        bank_allocated[bank_id] = bank_allocated.get(bank_id, 0) + edge["allocated_cash_minor"]
    order_rows = [
        row
        | {
            "allocated_cash_minor": order_allocated.get(row["order_id"], 0),
            "outstanding_minor": result["order_outstanding_minor"][row["order_id"]],
            "payment_status": result["payment_statuses"][row["order_id"]],
        }
        for row in result["orders"]
    ]
    bank_rows = [
        row
        | {
            "allocated_cash_minor": bank_allocated.get(row["bank_txn_id"], 0),
            "unapplied_minor": result["bank_unapplied_minor"].get(row["bank_txn_id"], 0),
        }
        for row in result["bank_transactions"]
    ]
    kpi_rows = [
        {"metric": key, "value": safe_excel_value(value), "revision": revision}
        for key, value in result["kpis"].items()
        if not isinstance(value, dict)
    ]
    group_rows = _safe_rows([row for row in result["groups"] if row["link_status"] == "CONFIRMED"])
    review_rows = _safe_rows([row for row in result["groups"] if row["link_status"] == "PROPOSED"])
    manifest_path = run_directory(run_id) / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest_rows = [
        {
            "key": key,
            "value": safe_excel_value(json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value),
        }
        for key, value in (manifest | {"effective_revision": revision}).items()
    ]
    sheets = {
        "01_TongQuan_KPI": kpi_rows,
        "02_Orders": _safe_rows(order_rows),
        "03_BankTransactions": _safe_rows(bank_rows),
        "04_ConfirmedGroups": group_rows,
        "05_AllocationEdges": _safe_rows(result["allocations"]),
        "06_ReviewQueue": review_rows,
        "07_Exceptions_Orphans": _safe_rows(result["exceptions"]),
        "08_ReviewAudit": [],
        "09_RunManifest": manifest_rows,
    }
    with pd.ExcelWriter(
        output,
        engine="xlsxwriter",
        engine_kwargs={"options": {"strings_to_formulas": False, "strings_to_urls": False}},
    ) as writer:
        for sheet_name, rows in sheets.items():
            frame = pd.DataFrame(rows)
            if frame.empty:
                frame = pd.DataFrame([{"message": "Không có dữ liệu ở revision này"}])
            frame.to_excel(writer, sheet_name=sheet_name, index=False)
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, len(frame), max(len(frame.columns) - 1, 0))
            for index, column in enumerate(frame.columns):
                width = min(
                    60,
                    max(
                        len(str(column)) + 2,
                        max((len(str(value)) for value in frame[column].head(200)), default=0) + 2,
                    ),
                )
                cell_format = None
                if str(column).endswith("_minor"):
                    cell_format = writer.book.add_format({"num_format": "#,##0;[Red]-#,##0"})
                worksheet.set_column(index, index, width, cell_format)
    return output
