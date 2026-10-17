"""Deterministic source-profile recognition and exact schema fingerprints."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from smartrecon.ingest.mapping import (
    BANK_FIELDS,
    BANK_REQUIRED,
    ORDER_FIELDS,
    ORDER_REQUIRED,
    analyze_mapping,
    normalize_column_name,
)
from smartrecon.ingest.readers import RawSourceBundle, RawTable

SCHEMA_VERSION = "smart-import-schema-2026-10-17"


@dataclass(frozen=True, slots=True)
class ProfileRecognition:
    """A conservative built-in classification; it never changes source values."""

    key: str
    name: str
    status: str
    reasons: tuple[str, ...]


def table_schema(table: RawTable) -> dict[str, Any]:
    """Return structure attributes that mapping and transformation assumptions depend on."""
    return {
        "columns": [str(column) for column in table.frame.columns],
        "header_depth": table.structure.selected.header_depth,
        "delimiter": table.structure.selected.delimiter,
    }


def source_schema(raw: RawSourceBundle) -> dict[str, Any]:
    """Describe both required feeds in stable order."""
    return {
        "schema_version": SCHEMA_VERSION,
        "orders": table_schema(raw.orders),
        "bank_transactions": table_schema(raw.bank_transactions),
    }


def schema_fingerprint(raw: RawSourceBundle) -> str:
    """Hash the exact two-feed schema so changed structures cannot reuse a saved profile."""
    payload = json.dumps(source_schema(raw), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def recognize_profiles(raw: RawSourceBundle) -> dict[str, dict[str, Any]]:
    """Recognize safe built-in shapes without inventing payout aggregation semantics."""
    order = _recognize_orders(raw.orders)
    bank = _recognize_bank(raw.bank_transactions)
    return {"orders": asdict(order), "bank_transactions": asdict(bank)}


def _recognize_orders(table: RawTable) -> ProfileRecognition:
    columns = {normalize_column_name(str(column)) for column in table.frame.columns}
    shopee_markers = {column for column in columns if "shopee" in column}
    payout_markers = {
        "ma_dot_quyet_toan",
        "settlement_id",
        "payout_id",
        "tong_tien_thanh_toan",
        "settlement_amount",
    }
    if shopee_markers and columns & payout_markers:
        return ProfileRecognition(
            "SHOPEE_PAYOUT_REVIEW_REQUIRED",
            "Shopee settlement/payout theo đợt",
            "UNSUPPORTED_AUTOMATIC_AGGREGATION",
            (
                "Phát hiện dấu hiệu Shopee và mã/tổng tiền quyết toán theo đợt",
                "Chưa có chính sách đã xác nhận cho phí, hoàn tiền, khấu trừ và đơn vị phải thu",
            ),
        )
    if shopee_markers:
        return ProfileRecognition(
            "SHOPEE_ORDER_LEVEL",
            "Shopee cấp đơn hàng",
            "NEEDS_REVIEW",
            ("Phát hiện cột đặc thù Shopee nhưng vẫn giữ nguyên từng dòng đơn hàng",),
        )
    analysis = analyze_mapping(
        table.frame,
        ORDER_FIELDS,
        feed="orders",
        required_fields=ORDER_REQUIRED,
    )
    status = "RECOGNIZED" if analysis.required_auto_selected == len(ORDER_REQUIRED) else "NEEDS_REVIEW"
    return ProfileRecognition(
        "GENERIC_RECEIVABLE",
        "Khoản phải thu thông dụng",
        status,
        (f"Tự ghép chắc chắn {analysis.required_auto_selected}/{len(ORDER_REQUIRED)} trường bắt buộc",),
    )


def _recognize_bank(table: RawTable) -> ProfileRecognition:
    analysis = analyze_mapping(
        table.frame,
        BANK_FIELDS,
        feed="bank_transactions",
        required_fields=BANK_REQUIRED,
    )
    cash_transformation = analysis.selected_transformations.get("cash_movement", {})
    if cash_transformation.get("type") == "SPLIT_CREDIT_DEBIT":
        return ProfileRecognition(
            "GENERIC_SPLIT_BANK_STATEMENT",
            "Sao kê tách cột ghi có/ghi nợ",
            "RECOGNIZED",
            ("Phát hiện duy nhất một cặp cột ghi có và ghi nợ rõ nghĩa",),
        )
    amount_basis = next(
        (str(column) for column in table.frame.columns if normalize_column_name(str(column)) == "amount_basis"),
        None,
    )
    if amount_basis:
        observed = {
            str(value).strip().upper()
            for value in table.frame[amount_basis].dropna().head(100).tolist()
            if str(value).strip()
        }
        if observed == {"NET_SETTLEMENT"}:
            return ProfileRecognition(
                "PSP_NET_SETTLEMENT",
                "PSP net settlement",
                "RECOGNIZED",
                ("Cột amount_basis chỉ chứa NET_SETTLEMENT trong mẫu kiểm tra",),
            )
    status = "RECOGNIZED" if analysis.required_auto_selected == len(BANK_REQUIRED) else "NEEDS_REVIEW"
    return ProfileRecognition(
        "GENERIC_BANK_STATEMENT",
        "Sao kê ngân hàng thông dụng",
        status,
        (f"Tự ghép chắc chắn {analysis.required_auto_selected}/{len(BANK_REQUIRED)} trường bắt buộc",),
    )
