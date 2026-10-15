"""Read-only transaction detail projections from one persisted run snapshot."""

from __future__ import annotations

from typing import Any

from backend.smartrecon_api.db.models import UploadSession
from backend.smartrecon_api.services.uploads import read_source_rows


def entity_detail(
    result: dict[str, Any],
    session: UploadSession,
    entity_type: str,
    entity_id: str,
) -> dict[str, Any] | None:
    """Build a traceable order, bank, group, or exception view without changing state."""
    groups = result["groups"]
    exceptions = result["exceptions"]
    if entity_type == "group":
        selected = next((item for item in groups if item["group_id"] == entity_id), None)
        if selected is None:
            return None
        order_ids = selected["order_ids"]
        bank_ids = selected["bank_txn_ids"]
        related_groups = [selected]
        selected_exception = None
    elif entity_type == "order":
        if not any(item["order_id"] == entity_id for item in result["orders"]):
            return None
        related_groups = [item for item in groups if entity_id in item["order_ids"]]
        order_ids = sorted({entity_id, *(order_id for item in related_groups for order_id in item["order_ids"])})
        bank_ids = sorted({bank_id for item in related_groups for bank_id in item["bank_txn_ids"]})
        selected_exception = None
    elif entity_type == "bank":
        if not any(item["bank_txn_id"] == entity_id for item in result["bank_transactions"]):
            return None
        related_groups = [item for item in groups if entity_id in item["bank_txn_ids"]]
        order_ids = sorted({order_id for item in related_groups for order_id in item["order_ids"]})
        bank_ids = sorted({entity_id, *(bank_id for item in related_groups for bank_id in item["bank_txn_ids"])})
        selected_exception = None
    elif entity_type == "exception":
        selected_exception = next((item for item in exceptions if item["exception_id"] == entity_id), None)
        if selected_exception is None:
            return None
        order_ids = selected_exception["order_ids"]
        bank_ids = selected_exception["bank_txn_ids"]
        related_groups = [
            item
            for item in groups
            if set(item["order_ids"]) & set(order_ids) or set(item["bank_txn_ids"]) & set(bank_ids)
        ]
    else:
        raise ValueError("Loại chi tiết không hợp lệ")

    orders = [item for item in result["orders"] if item["order_id"] in order_ids]
    banks = [item for item in result["bank_transactions"] if item["bank_txn_id"] in bank_ids]
    allocations = [
        item for item in result["allocations"] if item["order_id"] in order_ids or item["bank_txn_id"] in bank_ids
    ]
    adjustments = [item for item in result["adjustments"] if item["order_id"] in order_ids]
    related_exceptions = [
        item
        for item in exceptions
        if set(item["order_ids"]) & set(order_ids) or set(item["bank_txn_ids"]) & set(bank_ids)
    ]
    candidates = [
        item
        for item in result["candidates"]
        if set(item["order_ids"]) & set(order_ids) or set(item["bank_txn_ids"]) & set(bank_ids)
    ]
    enriched_orders = _enrich_records(session, "orders", orders)
    enriched_banks = _enrich_records(session, "bank_transactions", banks)
    allocated = sum(item["allocated_cash_minor"] for item in allocations)
    expected = sum(item["expected_amount_minor"] for item in orders)
    posted = sum(item["posted_amount_minor"] for item in banks)
    outstanding = sum(result["order_outstanding_minor"].get(item["order_id"], 0) for item in orders)
    unapplied = sum(result["bank_unapplied_minor"].get(item["bank_txn_id"], 0) for item in banks)
    link_statuses = {item["link_status"] for item in related_groups}
    link_status = (
        "CONFIRMED" if "CONFIRMED" in link_statuses else "PROPOSED" if "PROPOSED" in link_statuses else "UNMATCHED"
    )
    relationship_types = sorted({item["group_type"] for item in related_groups})
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "overview": {
            "link_status": link_status,
            "payment_statuses": {
                order_id: result["payment_statuses"].get(order_id, "UNKNOWN") for order_id in order_ids
            },
            "relationship_types": relationship_types,
            "expected_amount_minor": expected,
            "posted_amount_minor": posted,
            "allocated_cash_minor": allocated,
            "verified_adjustment_minor": sum(item["amount_minor"] for item in adjustments),
            "outstanding_minor": outstanding,
            "unapplied_minor": unapplied,
        },
        "orders": enriched_orders,
        "bank_transactions": enriched_banks,
        "groups": related_groups,
        "allocations": allocations,
        "adjustments": adjustments,
        "candidates": candidates,
        "exceptions": related_exceptions,
        "selected_exception": selected_exception,
        "guidance_vi": _guidance(
            selected_exception or next(iter(related_exceptions), None),
            link_status,
            outstanding,
            unapplied,
        ),
    }


def extend_group_detail(result: dict[str, Any], session: UploadSession, group_id: str) -> dict[str, Any] | None:
    detail = entity_detail(result, session, "group", group_id)
    if detail is None:
        return None
    group = detail["groups"][0]
    return group | {
        "allocations": detail["allocations"],
        "order_records": detail["orders"],
        "bank_transaction_records": detail["bank_transactions"],
        "adjustments": detail["adjustments"],
        "exceptions": detail["exceptions"],
        "candidates": detail["candidates"],
        "totals": detail["overview"],
    }


def _enrich_records(session: UploadSession, feed: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    row_numbers = [
        record.get("lineage", {}).get("source_row_number")
        for record in records
        if record.get("lineage", {}).get("source_row_number")
    ]
    raw_rows = read_source_rows(session, feed, row_numbers)
    file_key = "orders" if feed == "orders" else "bank"
    file_meta = session.source_manifest.get("files", {}).get(file_key, {})
    enriched: list[dict[str, Any]] = []
    for record in records:
        lineage = record.get("lineage") or {}
        row_number = lineage.get("source_row_number")
        normalized = {key: value for key, value in record.items() if key != "lineage"}
        enriched.append(
            normalized
            | {
                "source": {
                    "filename": file_meta.get("name"),
                    "sheet_name": file_meta.get("sheet"),
                    "row_number": row_number,
                    "row_hash": lineage.get("source_row_hash"),
                    "file_id": lineage.get("source_file_id"),
                    "raw_values": raw_rows.get(row_number, {}),
                },
            }
        )
    return enriched


def _guidance(
    exception: dict[str, Any] | None,
    link_status: str,
    outstanding_minor: int,
    unapplied_minor: int,
) -> str:
    if exception:
        codes = set(exception["reason_codes"])
        if "ORPHAN_BANK" in codes:
            return "Chưa tìm thấy đơn hàng tương ứng. Kiểm tra mã tham chiếu, kỳ dữ liệu và nguồn đơn hàng."
        if "NO_CONFIRMED_RECEIPT" in codes or "ORPHAN_INTERNAL" in codes:
            return "Chưa tìm thấy giao dịch thanh toán tương ứng. Kiểm tra kỳ sao kê và mã tham chiếu."
        if "PARTIAL_PAYMENT" in codes:
            return "Đã xác định giao dịch nhưng số tiền chưa đủ. Kiểm tra khoản còn thiếu và không tự coi là phí."
        if "OVERPAY_RESIDUAL" in codes:
            return "Đơn hàng đã đủ tiền nhưng còn tiền nhận chưa phân bổ. Xác minh cách xử lý số dư."
    if link_status == "PROPOSED":
        return "Đây là đề xuất ghép, chưa tạo khoản phân bổ tiền và chưa đi vào KPI đã xác nhận."
    if link_status == "UNMATCHED":
        return "Chưa tìm thấy giao dịch tương ứng với đủ bằng chứng để xác nhận."
    if outstanding_minor > 0:
        return "Đã xác định giao dịch nhưng số tiền chưa đủ. Kiểm tra khoản còn thiếu và không tự coi là phí."
    if unapplied_minor > 0:
        return "Đơn hàng đã đủ tiền nhưng còn tiền nhận chưa phân bổ. Xác minh cách xử lý số dư."
    return "Đối chiếu các bản ghi nguồn, khoản phân bổ và bằng chứng trước khi kết luận."
