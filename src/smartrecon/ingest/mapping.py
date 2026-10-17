"""Explainable, conservative source-to-canonical mapping suggestions."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

from smartrecon.domain.statuses import Currency

ORDER_REQUIRED = {"order_id", "ordered_at", "expected_amount"}
BANK_REQUIRED = {"bank_txn_id", "txn_date", "posted_amount", "direction", "amount_basis"}

ORDER_FIELDS = ORDER_REQUIRED | {
    "currency",
    "order_status",
    "external_ref",
    "customer_id",
    "customer_name",
    "payment_channel",
    "batch_ref",
    "description",
}
BANK_FIELDS = BANK_REQUIRED | {
    "currency",
    "txn_ref",
    "value_date",
    "description",
    "sender_name",
    "channel",
    "batch_ref",
    "declared_fee",
}
TRANSFORMATION_VERSION = "smart-import-2026-10-16"

ALIASES: dict[str, tuple[str, ...]] = {
    "order_id": (
        "order_id",
        "order_ref",
        "order_no",
        "order_number",
        "so_number",
        "so_no",
        "sales_order",
        "receivable_id",
        "invoice_id",
        "ma_dh",
        "ma_don_hang",
        "ma_khoan_phai_thu",
        "so_don_hang",
        "order_code",
    ),
    "ordered_at": (
        "ordered_at",
        "order_date",
        "created_date",
        "created_at",
        "tx_date",
        "ngay_tao",
        "ngay_dat_hang",
        "ngay_phat_sinh",
        "ngay_don_hang",
    ),
    "expected_amount": (
        "expected_amount",
        "amount",
        "amount_due",
        "balance_due",
        "order_amount",
        "receivable",
        "thanh_tien",
        "so_tien_can_thu",
        "so_tien_phai_thu",
        "gia_tri_don_hang",
        "tong_tien",
    ),
    "order_status": (
        "order_status",
        "status",
        "trang_thai",
        "trang_thai_don_hang",
        "trang_thai_khoan_thu",
    ),
    "bank_txn_id": (
        "bank_txn_id",
        "tx_id",
        "txn_id",
        "transaction_id",
        "transaction_no",
        "bank_id",
        "ma_gd",
        "ma_giao_dich",
        "so_giao_dich",
        "transaction_code",
    ),
    "txn_ref": (
        "txn_ref",
        "bank_ref",
        "reference",
        "reference_no",
        "ma_tham_chieu",
        "noi_dung_tham_chieu",
    ),
    "txn_date": (
        "txn_date",
        "clear_date",
        "posting_date",
        "posted_date",
        "transaction_date",
        "ngay_giao_dich",
        "ngay_hach_toan",
        "ngay_ghi_co",
    ),
    "value_date": ("value_date", "effective_date", "ngay_gia_tri", "ngay_hieu_luc"),
    "posted_amount": (
        "posted_amount",
        "transaction_amount",
        "net_amount",
        "credit_amount",
        "amount",
        "so_tien_giao_dich",
        "so_tien_ghi_co",
        "so_tien_thuc_nhan",
        "tien_vao",
    ),
    "direction": (
        "direction",
        "credit_debit",
        "debit_credit",
        "transaction_type",
        "chieu_giao_dich",
        "no_co",
    ),
    "amount_basis": ("amount_basis", "basis", "co_so_so_tien", "loai_so_tien"),
    "description": (
        "description",
        "memo",
        "narrative",
        "transaction_memo",
        "dien_giai",
        "noi_dung",
        "noi_dung_ck",
    ),
    "currency": ("currency", "currency_code", "ccy", "loai_tien", "ma_tien_te"),
    "external_ref": ("external_ref", "payment_ref", "invoice_ref", "ma_thanh_toan", "ma_hoa_don"),
    "customer_id": ("customer_id", "customer_code", "ma_khach_hang"),
    "customer_name": ("customer_name", "buyer_name", "ten_khach_hang"),
    "payment_channel": ("payment_channel", "payment_method", "channel", "kenh_thanh_toan"),
    "sender_name": ("sender_name", "payer_name", "remitter_name", "nguoi_chuyen", "ten_nguoi_chuyen"),
    "channel": ("channel", "payment_channel", "kenh_giao_dich", "kenh_thanh_toan"),
    "batch_ref": ("batch_ref", "settlement_ref", "payout_id", "ma_lo", "ma_dot_quyet_toan"),
    "declared_fee": ("declared_fee", "fee", "fee_amount", "phi_khai_bao", "phi_giao_dich"),
}

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)
_DIRECTION_VALUES = {"credit", "debit", "cr", "dr", "co", "no", "ghi_co", "ghi_no"}
_BASIS_VALUES = {"posted_cash", "net_settlement", "gross_settlement"}
_CURRENCY_VALUES = {"vnd", "brl"}
_STATUS_VALUES = {
    "eligible",
    "pending",
    "canceled",
    "cancelled",
    "excluded",
    "da_giao",
    "hoan_thanh",
    "da_huy",
    "cho_xu_ly",
}


def normalize_column_name(value: str) -> str:
    """Normalize separators and accents for deterministic name comparison."""
    decomposed = unicodedata.normalize("NFKD", value.strip().casefold())
    ascii_text = "".join(character for character in decomposed if not unicodedata.combining(character))
    ascii_text = ascii_text.replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")


@dataclass(frozen=True, slots=True)
class MappingConfig:
    """User-confirmed column and parsing semantics for both feeds."""

    order_columns: dict[str, str]
    bank_columns: dict[str, str]
    currency: Currency
    source_profile: str = "BANK_CREDIT"
    date_format: str = "%Y-%m-%d"
    decimal_separator: str = "."
    thousand_separator: str | None = ","
    order_defaults: dict[str, str] = field(default_factory=lambda: {"order_status": "ELIGIBLE"})
    bank_defaults: dict[str, str] = field(default_factory=dict)
    confirmed_structure: bool = False
    order_date_format: str | None = None
    bank_date_format: str | None = None
    order_transformations: dict[str, dict[str, Any]] = field(default_factory=dict)
    bank_transformations: dict[str, dict[str, Any]] = field(default_factory=dict)
    transformation_version: str = TRANSFORMATION_VERSION
    confirmed_ambiguities: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MappingCompetitor:
    source_column: str
    heuristic_score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MappingSuggestion:
    canonical_target: str
    source_column: str | None
    transformation: dict[str, Any] | None
    heuristic_score: int
    confidence: str
    reasons: tuple[str, ...]
    competitors: tuple[MappingCompetitor, ...]
    sample_before: tuple[str, ...]
    sample_after: tuple[str, ...]
    status: str


@dataclass(frozen=True, slots=True)
class MappingAnalysis:
    feed: str
    suggestions: tuple[MappingSuggestion, ...]
    selected_mapping: dict[str, str]
    selected_transformations: dict[str, dict[str, Any]]
    required_total: int
    required_auto_selected: int
    required_needs_review: int
    required_unsupported: int


@dataclass(frozen=True, slots=True)
class _ScoredColumn:
    source_column: str
    score: int
    reasons: tuple[str, ...]
    samples: tuple[str, ...]
    ambiguous_values: bool = False


def _values(frame: pd.DataFrame, column: str, limit: int = 100) -> list[str]:
    values: list[str] = []
    for value in frame[column].head(limit).tolist():
        if value is None or pd.isna(value):
            continue
        text = " ".join(unicodedata.normalize("NFKC", str(value)).strip().split())
        if text:
            values.append(text)
    return values


def _date_ratio(values: list[str]) -> tuple[float, bool]:
    if not values:
        return 0.0, False
    parsed = 0
    ambiguous = False
    for value in values:
        matched = False
        for date_format in _DATE_FORMATS:
            try:
                datetime.strptime(value, date_format)
                matched = True
                if date_format in {"%d/%m/%Y", "%d-%m-%Y"}:
                    day, month = map(int, re.split(r"[/-]", value)[:2])
                    ambiguous = ambiguous or (day <= 12 and month <= 12)
                break
            except ValueError:
                continue
        parsed += matched
    return parsed / len(values), ambiguous


def _money_ratio(values: list[str]) -> tuple[float, bool]:
    if not values:
        return 0.0, False
    parsed = 0
    ambiguous = False
    for value in values:
        compact = value.replace(" ", "")
        if re.fullmatch(r"[-+]?\d{1,3},\d{3}", compact):
            ambiguous = True
        candidates = {compact, compact.replace(",", ""), compact.replace(".", "").replace(",", ".")}
        if any(_is_decimal(candidate) for candidate in candidates):
            parsed += 1
    return parsed / len(values), ambiguous


def _is_decimal(value: str) -> bool:
    try:
        Decimal(value)
        return True
    except InvalidOperation:
        return False


def _enum_ratio(values: list[str], accepted: set[str]) -> float:
    if not values:
        return 0.0
    return sum(normalize_column_name(value) in accepted for value in values) / len(values)


def _name_evidence(column: str, canonical: str) -> tuple[int, list[str]]:
    normalized = normalize_column_name(column)
    canonical_name = normalize_column_name(canonical)
    if normalized == canonical_name:
        return 90, ["Tên cột trùng chính xác với trường chuẩn"]
    aliases = {normalize_column_name(alias) for alias in ALIASES.get(canonical, (canonical,))}
    if normalized in aliases:
        return 82, ["Tên cột khớp từ điển đồng nghĩa Việt/Anh"]
    source_tokens = set(normalized.split("_"))
    best_overlap = 0.0
    for alias in aliases:
        alias_tokens = set(alias.split("_"))
        if source_tokens and alias_tokens:
            best_overlap = max(best_overlap, len(source_tokens & alias_tokens) / len(source_tokens | alias_tokens))
    if best_overlap >= 0.66:
        return 48, ["Tên cột có cụm từ hoặc viết tắt gần với trường chuẩn"]
    return 0, []


def _value_evidence(canonical: str, values: list[str]) -> tuple[int, list[str], bool]:
    if not values:
        return 0, ["Cột không có giá trị mẫu để kiểm tra"], False
    reasons: list[str] = []
    ambiguous = False
    score = 0
    if canonical in {"ordered_at", "txn_date", "value_date"}:
        ratio, ambiguous = _date_ratio(values)
        score = round(24 * ratio)
        reasons.append(f"{round(ratio * 100)}% giá trị mẫu đọc được như ngày")
        if ambiguous:
            reasons.append("Có ngày dạng ngày/tháng có thể hiểu theo hai locale")
    elif canonical in {"expected_amount", "posted_amount", "declared_fee"}:
        ratio, ambiguous = _money_ratio(values)
        score = round(22 * ratio)
        reasons.append(f"{round(ratio * 100)}% giá trị mẫu có hình dạng số tiền")
        if ambiguous:
            reasons.append("Có cách viết số như 1,234 cần xác nhận dấu phân cách")
    elif canonical in {"order_id", "bank_txn_id", "txn_ref", "external_ref", "batch_ref", "customer_id"}:
        unique_ratio = len(set(values)) / len(values)
        score = round(20 * unique_ratio)
        reasons.append(f"Độ duy nhất trong mẫu là {round(unique_ratio * 100)}%")
    elif canonical == "direction":
        ratio = _enum_ratio(values, _DIRECTION_VALUES)
        score = round(26 * ratio)
        reasons.append(f"{round(ratio * 100)}% giá trị mẫu là ký hiệu tiền vào/ra đã biết")
    elif canonical == "amount_basis":
        ratio = _enum_ratio(values, _BASIS_VALUES)
        score = round(26 * ratio)
        reasons.append(f"{round(ratio * 100)}% giá trị mẫu nêu rõ cơ sở số tiền")
    elif canonical == "currency":
        ratio = _enum_ratio(values, _CURRENCY_VALUES)
        score = round(24 * ratio)
        reasons.append(f"{round(ratio * 100)}% giá trị mẫu là mã tiền tệ hỗ trợ")
    elif canonical == "order_status":
        ratio = _enum_ratio(values, _STATUS_VALUES)
        score = round(22 * ratio)
        reasons.append(f"{round(ratio * 100)}% giá trị mẫu giống trạng thái đơn hàng")
    elif canonical in {"description", "customer_name", "sender_name"}:
        average_length = sum(len(value) for value in values) / len(values)
        score = min(16, round(average_length / 2))
        reasons.append("Giá trị mẫu là văn bản mô tả")
    else:
        score = 8
        reasons.append("Cột có dữ liệu mẫu không trống")
    return score, reasons, ambiguous


def _score_column(
    frame: pd.DataFrame,
    column: str,
    canonical: str,
    profile_mapping: dict[str, str] | None,
) -> _ScoredColumn:
    samples = tuple(_values(frame, column)[:5])
    if profile_mapping and profile_mapping.get(canonical) == column:
        return _ScoredColumn(
            column,
            100,
            ("Khớp profile nhập liệu đã được người dùng xác nhận",),
            samples,
        )
    name_score, reasons = _name_evidence(column, canonical)
    value_score, value_reasons, ambiguous = _value_evidence(canonical, list(samples))
    if name_score == 0 and value_score < 18:
        return _ScoredColumn(column, 0, tuple(reasons + value_reasons), samples, ambiguous)
    score = min(100, name_score + value_score)
    return _ScoredColumn(column, score, tuple(reasons + value_reasons), samples, ambiguous)


def _confidence(score: int) -> str:
    if score >= 85:
        return "HIGH"
    if score >= 60:
        return "MEDIUM"
    return "LOW"


def analyze_mapping(
    frame: pd.DataFrame,
    canonical_fields: set[str],
    *,
    feed: str,
    required_fields: set[str],
    profile_mapping: dict[str, str] | None = None,
) -> MappingAnalysis:
    """Rank every mapping with evidence; scores are heuristics, not probabilities."""
    ranked_by_target: dict[str, list[_ScoredColumn]] = {}
    for canonical in sorted(canonical_fields):
        ranked_by_target[canonical] = sorted(
            (_score_column(frame, str(column), canonical, profile_mapping) for column in frame.columns),
            key=lambda candidate: (-candidate.score, candidate.source_column),
        )

    target_priority = sorted(
        canonical_fields,
        key=lambda canonical: (
            canonical not in required_fields,
            -(ranked_by_target[canonical][0].score if ranked_by_target[canonical] else 0),
            canonical,
        ),
    )
    assigned_sources: set[str] = set()
    selected: dict[str, _ScoredColumn] = {}
    for canonical in target_priority:
        selected_candidate = next(
            (candidate for candidate in ranked_by_target[canonical] if candidate.source_column not in assigned_sources),
            None,
        )
        if selected_candidate and selected_candidate.score > 0:
            selected[canonical] = selected_candidate
            assigned_sources.add(selected_candidate.source_column)

    suggestions: list[MappingSuggestion] = []
    selected_mapping: dict[str, str] = {}
    for canonical in sorted(canonical_fields):
        candidate = selected.get(canonical)
        ranked = ranked_by_target[canonical]
        competing = [item for item in ranked if not candidate or item.source_column != candidate.source_column][:3]
        if candidate is None:
            status = "unsupported" if canonical in required_fields else "needs-review"
            score = 0
            source_column = None
            reasons = ("Không có cột nguồn đủ bằng chứng để đề xuất",)
            samples: tuple[str, ...] = ()
        else:
            runner_up_score = competing[0].score if competing else 0
            margin = candidate.score - runner_up_score
            exact_or_profile = any(
                "trùng chính xác" in reason or "đồng nghĩa" in reason or "profile" in reason
                for reason in candidate.reasons
            )
            auto_selected = (
                candidate.score >= 85
                and margin >= 8
                and not candidate.ambiguous_values
                and (exact_or_profile or candidate.score >= 92)
            )
            status = "auto-selected" if auto_selected else "needs-review"
            score = candidate.score
            source_column = candidate.source_column
            reasons = candidate.reasons + ((f"Cách biệt {margin} điểm với ứng viên gần nhất",) if competing else ())
            samples = candidate.samples
            if status == "auto-selected":
                selected_mapping[canonical] = candidate.source_column
        suggestions.append(
            MappingSuggestion(
                canonical_target=canonical,
                source_column=source_column,
                transformation={"type": "DIRECT"} if source_column else None,
                heuristic_score=score,
                confidence=_confidence(score),
                reasons=reasons,
                competitors=tuple(
                    MappingCompetitor(item.source_column, item.score, item.reasons)
                    for item in competing
                    if item.score > 0
                ),
                sample_before=samples,
                sample_after=tuple(" ".join(value.split()) for value in samples),
                status=status,
            )
        )

    selected_transformations: dict[str, dict[str, Any]] = {}
    split = _split_credit_debit_columns(frame) if feed == "bank_transactions" else None
    if split and {"posted_amount", "direction"} <= canonical_fields:
        credit_column, debit_column = split
        specification: dict[str, Any] = {
            "type": "SPLIT_CREDIT_DEBIT",
            "credit_column": credit_column,
            "debit_column": debit_column,
        }
        selected_transformations["cash_movement"] = specification
        selected_mapping.pop("posted_amount", None)
        selected_mapping.pop("direction", None)
        split_samples = _split_samples(frame, credit_column, debit_column)
        replacements = {
            "posted_amount": MappingSuggestion(
                canonical_target="posted_amount",
                source_column=None,
                transformation=specification,
                heuristic_score=96,
                confidence="HIGH",
                reasons=(
                    "Phát hiện cặp cột tiền ghi có và tiền ghi nợ có tên rõ ràng",
                    "Số tiền được lấy từ đúng một phía có giá trị khác 0 trên từng dòng",
                ),
                competitors=(),
                sample_before=split_samples[0],
                sample_after=split_samples[1],
                status="auto-selected",
            ),
            "direction": MappingSuggestion(
                canonical_target="direction",
                source_column=None,
                transformation=specification,
                heuristic_score=96,
                confidence="HIGH",
                reasons=(
                    "Chiều giao dịch được dựng từ cột ghi có/ghi nợ, không suy từ dấu âm",
                    "Dòng có cả hai phía khác 0 sẽ bị Health Gate chặn",
                ),
                competitors=(),
                sample_before=split_samples[0],
                sample_after=split_samples[1],
                status="auto-selected",
            ),
        }
        suggestions = [replacements.get(item.canonical_target, item) for item in suggestions]

    required = [suggestion for suggestion in suggestions if suggestion.canonical_target in required_fields]
    return MappingAnalysis(
        feed=feed,
        suggestions=tuple(suggestions),
        selected_mapping=selected_mapping,
        selected_transformations=selected_transformations,
        required_total=len(required),
        required_auto_selected=sum(item.status == "auto-selected" for item in required),
        required_needs_review=sum(item.status == "needs-review" for item in required),
        required_unsupported=sum(item.status == "unsupported" for item in required),
    )


def _split_credit_debit_columns(frame: pd.DataFrame) -> tuple[str, str] | None:
    credit_names = {
        "credit",
        "credit_amount",
        "amount_credit",
        "ghi_co",
        "so_tien_ghi_co",
        "tien_vao",
    }
    debit_names = {
        "debit",
        "debit_amount",
        "amount_debit",
        "ghi_no",
        "so_tien_ghi_no",
        "tien_ra",
    }
    credits = [str(column) for column in frame.columns if normalize_column_name(str(column)) in credit_names]
    debits = [str(column) for column in frame.columns if normalize_column_name(str(column)) in debit_names]
    if len(credits) == 1 and len(debits) == 1 and credits[0] != debits[0]:
        return credits[0], debits[0]
    return None


def _split_samples(
    frame: pd.DataFrame, credit_column: str, debit_column: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    before: list[str] = []
    after: list[str] = []
    for _, row in frame[[credit_column, debit_column]].head(5).iterrows():
        credit = "" if pd.isna(row[credit_column]) else str(row[credit_column]).strip()
        debit = "" if pd.isna(row[debit_column]) else str(row[debit_column]).strip()
        before.append(f"ghi có={credit or 'trống'}; ghi nợ={debit or 'trống'}")
        if credit and credit not in {"0", "0.0", "0,0"} and not debit:
            after.append(f"CREDIT {credit}")
        elif debit and debit not in {"0", "0.0", "0,0"} and not credit:
            after.append(f"DEBIT {debit}")
        else:
            after.append("Cần kiểm tra")
    return tuple(before), tuple(after)


def suggest_mapping(columns: list[str], canonical_fields: set[str]) -> dict[str, str]:
    """Compatibility helper returning only unambiguous exact-name/alias suggestions."""
    normalized: dict[str, list[str]] = {}
    for column in columns:
        normalized.setdefault(normalize_column_name(column), []).append(column)
    suggestions: dict[str, str] = {}
    used: set[str] = set()
    for canonical in sorted(canonical_fields):
        for alias in ALIASES.get(canonical, (canonical,)):
            candidates = normalized.get(normalize_column_name(alias), [])
            if len(candidates) == 1 and candidates[0] not in used:
                suggestions[canonical] = candidates[0]
                used.add(candidates[0])
                break
    return suggestions


def default_demo_mapping() -> MappingConfig:
    """Return the explicit contract used by the generated demo files."""
    return MappingConfig(
        order_columns={
            "order_id": "order_id",
            "ordered_at": "ordered_at",
            "expected_amount": "expected_amount",
            "currency": "currency",
            "order_status": "order_status",
            "customer_name": "customer_name",
            "payment_channel": "payment_channel",
            "external_ref": "external_ref",
            "description": "description",
        },
        bank_columns={
            "bank_txn_id": "bank_txn_id",
            "txn_ref": "txn_ref",
            "txn_date": "txn_date",
            "value_date": "value_date",
            "direction": "direction",
            "posted_amount": "posted_amount",
            "currency": "currency",
            "amount_basis": "amount_basis",
            "description": "description",
            "sender_name": "sender_name",
            "channel": "channel",
            "batch_ref": "batch_ref",
            "declared_fee": "declared_fee",
        },
        currency=Currency.VND,
    )
