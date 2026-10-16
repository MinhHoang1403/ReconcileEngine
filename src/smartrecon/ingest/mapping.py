"""Explicit source-to-canonical mapping contracts and conservative suggestions."""

import re
import unicodedata
from dataclasses import dataclass, field

from smartrecon.domain.statuses import Currency

ORDER_REQUIRED = {"order_id", "ordered_at", "expected_amount"}
BANK_REQUIRED = {
    "bank_txn_id",
    "txn_date",
    "posted_amount",
    "direction",
    "amount_basis",
}

ALIASES: dict[str, tuple[str, ...]] = {
    "order_id": (
        "order_id",
        "order_ref",
        "receivable_id",
        "invoice_id",
        "ma_don_hang",
        "ma_khoan_phai_thu",
        "so_don_hang",
        "order_code",
    ),
    "ordered_at": (
        "ordered_at",
        "order_date",
        "tx_date",
        "created_at",
        "ngay_dat_hang",
        "ngay_phat_sinh",
        "ngay_don_hang",
    ),
    "expected_amount": (
        "expected_amount",
        "amount",
        "order_amount",
        "receivable",
        "so_tien_can_thu",
        "so_tien_phai_thu",
        "gia_tri_don_hang",
        "tong_tien",
    ),
    "order_status": ("order_status", "status", "trang_thai_don_hang", "trang_thai_khoan_thu"),
    "bank_txn_id": (
        "bank_txn_id",
        "tx_id",
        "transaction_id",
        "bank_id",
        "ma_giao_dich",
        "so_giao_dich",
        "transaction_code",
    ),
    "txn_ref": ("txn_ref", "bank_ref", "reference", "ma_tham_chieu", "noi_dung_tham_chieu"),
    "txn_date": (
        "txn_date",
        "clear_date",
        "posting_date",
        "transaction_date",
        "ngay_giao_dich",
        "ngay_hach_toan",
        "ngay_ghi_co",
    ),
    "value_date": ("value_date", "effective_date", "ngay_gia_tri", "ngay_hieu_luc"),
    "posted_amount": (
        "posted_amount",
        "net_amount",
        "credit_amount",
        "amount",
        "so_tien_giao_dich",
        "so_tien_ghi_co",
        "so_tien_thuc_nhan",
    ),
    "direction": ("direction", "credit_debit", "transaction_type", "chieu_giao_dich", "no_co"),
    "amount_basis": ("amount_basis", "basis", "co_so_so_tien", "loai_so_tien"),
    "description": ("description", "memo", "narrative", "dien_giai", "noi_dung"),
    "currency": ("currency", "currency_code", "loai_tien", "ma_tien_te"),
    "external_ref": ("external_ref", "payment_ref", "invoice_ref", "ma_thanh_toan", "ma_hoa_don"),
    "customer_id": ("customer_id", "ma_khach_hang"),
    "customer_name": ("customer_name", "sender_name", "payer_name", "ten_khach_hang", "nguoi_chuyen"),
    "payment_channel": ("payment_channel", "payment_method", "channel", "kenh_thanh_toan"),
    "sender_name": ("sender_name", "payer_name", "nguoi_chuyen", "ten_nguoi_chuyen"),
    "channel": ("channel", "payment_channel", "kenh_giao_dich", "kenh_thanh_toan"),
    "batch_ref": ("batch_ref", "settlement_ref", "ma_lo", "ma_dot_quyet_toan"),
    "declared_fee": ("declared_fee", "fee", "fee_amount", "phi_khai_bao", "phi_giao_dich"),
}


def normalize_column_name(value: str) -> str:
    """Normalize separators and accents for exact alias lookup, never fuzzy matching."""
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


def suggest_mapping(columns: list[str], canonical_fields: set[str]) -> dict[str, str]:
    """Suggest only exact normalized aliases; a user must still confirm them."""
    normalized: dict[str, list[str]] = {}
    for column in columns:
        normalized.setdefault(normalize_column_name(column), []).append(column)
    suggestions: dict[str, str] = {}
    for canonical in sorted(canonical_fields):
        for alias in ALIASES.get(canonical, (canonical,)):
            candidates = normalized.get(normalize_column_name(alias), [])
            if len(candidates) == 1:
                suggestions[canonical] = candidates[0]
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
