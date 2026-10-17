"""Explicit mapping and normalization from raw rows to canonical domain records."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from smartrecon.domain.models import BankTransaction, Order, SourceLineage
from smartrecon.domain.money import MoneyParseError, parse_minor_units
from smartrecon.domain.statuses import AmountBasis, Currency, Direction, OrderStatus, Severity
from smartrecon.ingest.mapping import BANK_REQUIRED, ORDER_REQUIRED, MappingConfig, normalize_column_name
from smartrecon.ingest.readers import RawSourceBundle, RawTable


@dataclass(frozen=True, slots=True)
class DataIssue:
    code: str
    severity: Severity
    feed: str
    message_vi: str
    source_rows: tuple[int, ...] = ()
    sample_values: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RejectedRow:
    feed: str
    source_row_number: int
    source_row_hash: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class NormalizedBundle:
    orders: tuple[Order, ...]
    bank_transactions: tuple[BankTransaction, ...]
    issues: tuple[DataIssue, ...]
    rejected_rows: tuple[RejectedRow, ...]
    duplicate_bank_ids: tuple[str, ...]
    source_hashes: dict[str, str]


def normalize_text(value: object) -> str:
    """Normalize Unicode/whitespace while retaining punctuation for evidence parsing."""
    if value is None or pd.isna(value):
        return ""
    return " ".join(unicodedata.normalize("NFKC", str(value)).strip().split())


def normalize_identifier(value: object) -> str:
    """Preserve meaningful characters and leading zeros in source identifiers."""
    return normalize_text(value)


def _row_hash(row: pd.Series) -> str:
    payload = {str(key): normalize_text(value) for key, value in row.items()}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _parse_date(value: object, date_format: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = normalize_text(value)
    if not raw:
        raise ValueError("Ngày bị trống")
    if date_format == "AUTO":
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except ValueError:
            pass
        if re.fullmatch(r"\d{4}/\d{1,2}/\d{1,2}", raw):
            return datetime.strptime(raw, "%Y/%m/%d").date()
        match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
        if match:
            first, second = int(match.group(1)), int(match.group(2))
            if first <= 12 and second <= 12:
                raise ValueError(f"Ngày mơ hồ cần xác nhận format: {raw!r}")
            if first > 12 and second <= 12:
                return datetime.strptime(raw, "%d/%m/%Y").date()
        raise ValueError(f"Không thể tự nhận diện ngày một cách an toàn: {raw!r}")
    return datetime.strptime(raw, date_format).date()


def _optional(row: pd.Series, columns: dict[str, str], field: str) -> str | None:
    source = columns.get(field)
    if not source:
        return None
    value = normalize_text(row[source])
    return value or None


def _money_samples(row: pd.Series, columns: dict[str, str], fields: tuple[str, ...]) -> tuple[str, ...]:
    """Return non-empty source money values for row-level Health Gate evidence."""
    values = [normalize_text(row[columns[field]]) for field in fields if columns.get(field)]
    return tuple(dict.fromkeys(value for value in values if value))


def _mapped_value(value: str, specification: dict[str, object] | None) -> str:
    """Apply only an explicit, persisted categorical value map."""
    if not specification or specification.get("type") != "VALUE_MAP":
        return value
    raw_map = specification.get("values", {})
    if not isinstance(raw_map, dict):
        raise ValueError("VALUE_MAP phải chứa object values")
    normalized_map = {normalize_column_name(str(key)): str(mapped) for key, mapped in raw_map.items()}
    key = normalize_column_name(value)
    if key not in normalized_map:
        raise ValueError(f"Giá trị chưa có trong bảng chuyển đổi đã xác nhận: {value!r}")
    return normalized_map[key]


def _parse_optional_minor(
    value: object,
    currency: Currency,
    mapping: MappingConfig,
) -> int:
    text = normalize_text(value)
    if not text:
        return 0
    return parse_minor_units(
        text,
        currency,
        decimal_separator=mapping.decimal_separator,
        thousand_separator=mapping.thousand_separator,
    )


def _bank_cash_values(row: pd.Series, mapping: MappingConfig, currency: Currency) -> tuple[int, Direction]:
    specification = mapping.bank_transformations.get("cash_movement")
    if specification:
        transformation_type = specification.get("type")
        if transformation_type == "SPLIT_CREDIT_DEBIT":
            credit_column = str(specification.get("credit_column", ""))
            debit_column = str(specification.get("debit_column", ""))
            credit = _parse_optional_minor(row[credit_column], currency, mapping)
            debit = _parse_optional_minor(row[debit_column], currency, mapping)
            if credit > 0 and debit > 0:
                raise ValueError("Cả cột ghi có và ghi nợ đều có số tiền khác 0")
            if credit == 0 and debit == 0:
                raise ValueError("Không xác định được chiều giao dịch từ hai cột ghi có/ghi nợ")
            return (credit, Direction.CREDIT) if credit > 0 else (debit, Direction.DEBIT)
        if transformation_type == "SIGNED_AMOUNT":
            source_column = str(specification.get("source_column", ""))
            positive_direction = Direction(str(specification.get("positive_direction", "")))
            negative_direction = Direction.DEBIT if positive_direction is Direction.CREDIT else Direction.CREDIT
            raw = normalize_text(row[source_column])
            if not raw:
                raise ValueError("Số tiền có dấu bị trống")
            negative = raw.startswith("-")
            unsigned = raw[1:] if raw[:1] in {"-", "+"} else raw
            amount = parse_minor_units(
                unsigned,
                currency,
                decimal_separator=mapping.decimal_separator,
                thousand_separator=mapping.thousand_separator,
            )
            if amount == 0:
                raise ValueError("Không thể suy ra chiều giao dịch từ số tiền bằng 0")
            return amount, negative_direction if negative else positive_direction
        raise ValueError(f"Transformation tiền không được hỗ trợ: {transformation_type}")

    amount = parse_minor_units(
        row[mapping.bank_columns["posted_amount"]],
        currency,
        decimal_separator=mapping.decimal_separator,
        thousand_separator=mapping.thousand_separator,
    )
    direction_raw = _optional(row, mapping.bank_columns, "direction") or mapping.bank_defaults.get("direction", "")
    direction = _mapped_value(direction_raw, mapping.bank_transformations.get("direction"))
    return amount, Direction(direction.upper())


def _bank_money_samples(row: pd.Series, mapping: MappingConfig) -> tuple[str, ...]:
    values = list(_money_samples(row, mapping.bank_columns, ("posted_amount", "declared_fee")))
    cash_specification = mapping.bank_transformations.get("cash_movement", {})
    for key in ("credit_column", "debit_column", "source_column"):
        source = cash_specification.get(key)
        if source and source in row:
            value = normalize_text(row[str(source)])
            if value:
                values.append(value)
    return tuple(dict.fromkeys(values))


def _validate_mapping(
    table: RawTable,
    columns: dict[str, str],
    required: set[str],
    feed: str,
    transformations: dict[str, dict[str, object]],
) -> list[DataIssue]:
    issues: list[DataIssue] = []
    covered_by_transformation: set[str] = set()
    transformation_sources: set[str] = set()
    for specification in transformations.values():
        transformation_type = str(specification.get("type", ""))
        if transformation_type == "SPLIT_CREDIT_DEBIT":
            covered_by_transformation.update({"posted_amount", "direction"})
            transformation_sources.update(str(specification.get(key, "")) for key in ("credit_column", "debit_column"))
        elif transformation_type == "SIGNED_AMOUNT":
            covered_by_transformation.update({"posted_amount", "direction"})
            transformation_sources.add(str(specification.get("source_column", "")))
        elif transformation_type == "VALUE_MAP":
            continue
        else:
            issues.append(
                DataIssue(
                    "UNSUPPORTED_TRANSFORMATION",
                    Severity.BLOCKING,
                    feed,
                    f"Transformation không được hỗ trợ: {transformation_type or '(trống)'}",
                )
            )
    if "cash_movement" in transformations and {"posted_amount", "direction"} & columns.keys():
        issues.append(
            DataIssue(
                "TRANSFORMATION_CONFLICT",
                Severity.BLOCKING,
                feed,
                "Không được đồng thời map trực tiếp và biến đổi cho số tiền/chiều giao dịch.",
            )
        )
    transformation_sources.discard("")
    missing_mapping = sorted(required - set(columns) - covered_by_transformation)
    if missing_mapping:
        issues.append(
            DataIssue(
                "MISSING_MAPPING",
                Severity.BLOCKING,
                feed,
                f"Chưa map trường bắt buộc: {', '.join(missing_mapping)}",
            )
        )
    absent_columns = sorted(
        {source for source in set(columns.values()) | transformation_sources if source not in table.frame.columns}
    )
    if absent_columns:
        issues.append(
            DataIssue(
                "SOURCE_COLUMN_NOT_FOUND",
                Severity.BLOCKING,
                feed,
                f"Không tìm thấy cột nguồn: {', '.join(absent_columns)}",
            )
        )
    selected: dict[str, list[str]] = {}
    for canonical, source in columns.items():
        if source:
            selected.setdefault(source, []).append(canonical)
    for source in transformation_sources:
        selected.setdefault(source, []).append("transformation")
    conflicts = {source: fields for source, fields in selected.items() if len(fields) > 1}
    if conflicts:
        explanation = "; ".join(
            f"cột '{source}' đang dùng cho {', '.join(sorted(fields))}" for source, fields in sorted(conflicts.items())
        )
        issues.append(
            DataIssue(
                "SOURCE_COLUMN_REUSED",
                Severity.BLOCKING,
                feed,
                f"Một cột nguồn không thể đại diện cho nhiều trường chuẩn: {explanation}.",
            )
        )
    return issues


def normalize_bundle(raw: RawSourceBundle, mapping: MappingConfig) -> NormalizedBundle:
    """Create canonical rows, retaining all row-level parse failures for Health Gate."""
    issues = _validate_mapping(
        raw.orders,
        mapping.order_columns,
        ORDER_REQUIRED,
        "orders",
        mapping.order_transformations,
    )
    issues += _validate_mapping(
        raw.bank_transactions,
        mapping.bank_columns,
        BANK_REQUIRED,
        "bank_transactions",
        mapping.bank_transformations,
    )
    if any(issue.severity is Severity.BLOCKING for issue in issues):
        return NormalizedBundle(
            (),
            (),
            tuple(issues),
            (),
            (),
            {
                "orders": raw.orders.file_sha256,
                "bank_transactions": raw.bank_transactions.file_sha256,
            },
        )

    orders: list[Order] = []
    banks: list[BankTransaction] = []
    rejected: list[RejectedRow] = []

    for position, (_, row) in enumerate(raw.orders.frame.iterrows()):
        row_number = raw.orders.source_row_numbers[position]
        row_digest = _row_hash(row)
        try:
            order_id = normalize_identifier(row[mapping.order_columns["order_id"]])
            if not order_id:
                raise ValueError("order_id bị trống")
            currency = _row_currency(row, mapping.order_columns, mapping.currency)
            amount = parse_minor_units(
                row[mapping.order_columns["expected_amount"]],
                currency,
                decimal_separator=mapping.decimal_separator,
                thousand_separator=mapping.thousand_separator,
            )
            status_raw = _optional(row, mapping.order_columns, "order_status") or mapping.order_defaults.get(
                "order_status", ""
            )
            status = _mapped_value(status_raw, mapping.order_transformations.get("order_status"))
            order_date_format = mapping.order_date_format or mapping.date_format
            orders.append(
                Order(
                    order_id=order_id,
                    ordered_at=_parse_date(row[mapping.order_columns["ordered_at"]], order_date_format),
                    expected_amount_minor=amount,
                    currency=currency,
                    order_status=OrderStatus(status.upper()),
                    external_ref=_optional(row, mapping.order_columns, "external_ref"),
                    customer_id=_optional(row, mapping.order_columns, "customer_id"),
                    customer_name=_optional(row, mapping.order_columns, "customer_name"),
                    payment_channel=_optional(row, mapping.order_columns, "payment_channel"),
                    batch_ref=_optional(row, mapping.order_columns, "batch_ref"),
                    description=_optional(row, mapping.order_columns, "description"),
                    lineage=SourceLineage(raw.orders.source_file_id, row_number, row_digest),
                )
            )
        except (KeyError, ValueError, MoneyParseError) as exc:
            issues.append(
                DataIssue(
                    "ORDER_PARSE_ERROR",
                    Severity.BLOCKING,
                    "orders",
                    f"Dòng {row_number} không chuẩn hóa được: {exc}",
                    (row_number,),
                    _money_samples(row, mapping.order_columns, ("expected_amount",)),
                )
            )
            rejected.append(RejectedRow("orders", row_number, row_digest, "ORDER_PARSE_ERROR"))

    for position, (_, row) in enumerate(raw.bank_transactions.frame.iterrows()):
        row_number = raw.bank_transactions.source_row_numbers[position]
        row_digest = _row_hash(row)
        try:
            bank_id = normalize_identifier(row[mapping.bank_columns["bank_txn_id"]])
            if not bank_id:
                raise ValueError("bank_txn_id bị trống")
            currency = _row_currency(row, mapping.bank_columns, mapping.currency)
            amount, direction = _bank_cash_values(row, mapping, currency)
            fee_raw = _optional(row, mapping.bank_columns, "declared_fee")
            declared_fee = (
                parse_minor_units(
                    fee_raw,
                    currency,
                    decimal_separator=mapping.decimal_separator,
                    thousand_separator=mapping.thousand_separator,
                )
                if fee_raw
                else None
            )
            value_date_raw = _optional(row, mapping.bank_columns, "value_date")
            bank_date_format = mapping.bank_date_format or mapping.date_format
            basis_raw = _optional(row, mapping.bank_columns, "amount_basis") or mapping.bank_defaults.get(
                "amount_basis", ""
            )
            basis = _mapped_value(basis_raw, mapping.bank_transformations.get("amount_basis"))
            banks.append(
                BankTransaction(
                    bank_txn_id=bank_id,
                    txn_ref=_optional(row, mapping.bank_columns, "txn_ref"),
                    txn_date=_parse_date(row[mapping.bank_columns["txn_date"]], bank_date_format),
                    value_date=(_parse_date(value_date_raw, bank_date_format) if value_date_raw else None),
                    posted_amount_minor=amount,
                    direction=direction,
                    amount_basis=AmountBasis(basis.upper()),
                    currency=currency,
                    description=_optional(row, mapping.bank_columns, "description"),
                    sender_name=_optional(row, mapping.bank_columns, "sender_name"),
                    channel=_optional(row, mapping.bank_columns, "channel"),
                    batch_ref=_optional(row, mapping.bank_columns, "batch_ref"),
                    declared_fee_minor=declared_fee,
                    lineage=SourceLineage(raw.bank_transactions.source_file_id, row_number, row_digest),
                )
            )
        except (KeyError, ValueError, MoneyParseError) as exc:
            issues.append(
                DataIssue(
                    "BANK_PARSE_ERROR",
                    Severity.BLOCKING,
                    "bank_transactions",
                    f"Dòng {row_number} không chuẩn hóa được: {exc}",
                    (row_number,),
                    _bank_money_samples(row, mapping),
                )
            )
            rejected.append(RejectedRow("bank_transactions", row_number, row_digest, "BANK_PARSE_ERROR"))

    duplicate_ids = _add_semantic_issues(orders, banks, issues)
    return NormalizedBundle(
        tuple(orders),
        tuple(banks),
        tuple(issues),
        tuple(rejected),
        tuple(sorted(duplicate_ids)),
        {
            "orders": raw.orders.file_sha256,
            "bank_transactions": raw.bank_transactions.file_sha256,
        },
    )


def _row_currency(row: pd.Series, columns: dict[str, str], configured_currency: Currency) -> Currency:
    raw = _optional(row, columns, "currency")
    return Currency(raw.upper()) if raw else configured_currency


def _add_semantic_issues(orders: list[Order], banks: list[BankTransaction], issues: list[DataIssue]) -> set[str]:
    duplicate_bank_ids: set[str] = set()
    order_ids: dict[str, list[int]] = {}
    for order in orders:
        row_number = order.lineage.source_row_number if order.lineage else 0
        order_ids.setdefault(order.order_id, []).append(row_number)
    for order_id, rows in order_ids.items():
        if len(rows) > 1:
            issues.append(
                DataIssue(
                    "ORDER_ID_COLLISION",
                    Severity.BLOCKING,
                    "orders",
                    f"order_id bị trùng và cần composite key hoặc sửa nguồn: {order_id}",
                    tuple(rows),
                )
            )

    bank_ids: dict[str, list[int]] = {}
    fingerprint_owner: dict[tuple[str | None, int, date, Direction], BankTransaction] = {}
    for bank in banks:
        bank_ids.setdefault(bank.bank_txn_id, []).append(bank.lineage.source_row_number if bank.lineage else 0)
        # Amount/date coincidence without a stable source reference is not
        # sufficient evidence of re-import; two legitimate credits can share it.
        if bank.txn_ref:
            fingerprint = (bank.txn_ref, bank.posted_amount_minor, bank.txn_date, bank.direction)
            owner = fingerprint_owner.get(fingerprint)
            if owner and owner.bank_txn_id != bank.bank_txn_id:
                duplicate_bank_ids.add(bank.bank_txn_id)
                issues.append(
                    DataIssue(
                        "POSSIBLE_REIMPORT",
                        Severity.WARNING,
                        "bank_transactions",
                        (
                            f"Giao dịch {bank.bank_txn_id} có fingerprint giống "
                            f"{owner.bank_txn_id}; cần xác minh trước khi dùng cash."
                        ),
                        tuple(
                            row
                            for row in (
                                owner.lineage.source_row_number if owner.lineage else 0,
                                bank.lineage.source_row_number if bank.lineage else 0,
                            )
                            if row
                        ),
                        (owner.bank_txn_id, bank.bank_txn_id),
                    )
                )
            else:
                fingerprint_owner[fingerprint] = bank
        if bank.amount_basis is AmountBasis.GROSS_SETTLEMENT:
            issues.append(
                DataIssue(
                    "GROSS_NOT_POSTED_CASH",
                    Severity.BLOCKING,
                    "bank_transactions",
                    f"{bank.bank_txn_id} là gross settlement, không phải cash đã ghi có.",
                    (bank.lineage.source_row_number if bank.lineage else 0,),
                )
            )
        if not bank.description and not bank.txn_ref:
            issues.append(
                DataIssue(
                    "MISSING_REFERENCE_EVIDENCE",
                    Severity.WARNING,
                    "bank_transactions",
                    f"{bank.bank_txn_id} không có memo hoặc reference để tạo bằng chứng mạnh.",
                    (bank.lineage.source_row_number if bank.lineage else 0,),
                )
            )

    for bank_id, rows in bank_ids.items():
        if len(rows) > 1:
            issues.append(
                DataIssue(
                    "BANK_ID_COLLISION",
                    Severity.BLOCKING,
                    "bank_transactions",
                    f"bank_txn_id canonical bị trùng: {bank_id}",
                    tuple(rows),
                )
            )

    currencies = {order.currency for order in orders} | {bank.currency for bank in banks}
    if len(currencies) > 1:
        issues.append(
            DataIssue(
                "CURRENCY_MISMATCH",
                Severity.BLOCKING,
                "all",
                "Một run chỉ được chứa một currency; hãy tách nguồn hoặc sửa mapping.",
                sample_values=tuple(sorted(currency.value for currency in currencies)),
            )
        )
    issues.append(
        DataIssue(
            "DATASET_SUMMARY",
            Severity.INFO,
            "all",
            f"Đã chuẩn hóa {len(orders)} orders và {len(banks)} bank rows.",
        )
    )
    return duplicate_bank_ids
