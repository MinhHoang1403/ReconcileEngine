"""Upload persistence, inspection, mapping, and Health Gate orchestration."""

from __future__ import annotations

import csv
import shutil
from dataclasses import asdict
from io import StringIO
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.smartrecon_api.db.models import ArtifactManifest, ImportProfile, UploadSession
from backend.smartrecon_api.schemas.uploads import MappingRequest, ResolutionRequest
from backend.smartrecon_api.services.artifacts import (
    relative_artifact_path,
    resolve_artifact_path,
    upload_directory,
)
from backend.smartrecon_api.services.serialization import to_jsonable
from smartrecon.domain.statuses import Severity
from smartrecon.ingest.eda import eda_to_dict, summarize_raw, summarize_standardized
from smartrecon.ingest.health import Exclusion, apply_exclusions, build_health_report
from smartrecon.ingest.mapping import (
    BANK_FIELDS,
    BANK_REQUIRED,
    ORDER_FIELDS,
    ORDER_REQUIRED,
    MappingConfig,
    analyze_mapping,
    default_demo_mapping,
)
from smartrecon.ingest.normalization import NormalizedBundle, normalize_bundle
from smartrecon.ingest.profiles import SCHEMA_VERSION, recognize_profiles, schema_fingerprint, source_schema
from smartrecon.ingest.readers import MAX_FILE_BYTES, RawSourceBundle, read_source_bundle

ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
}


async def save_upload(upload: UploadFile, directory: Path, target_name: str) -> Path:
    """Stream an upload to a server-chosen path with a hard byte limit."""
    if not upload.filename:
        raise ValueError("Upload thiếu tên file")
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise ValueError("Chỉ hỗ trợ CSV hoặc XLSX")
    if upload.content_type and upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"Content-Type không được hỗ trợ: {upload.content_type}")
    path = directory / f"{target_name}{suffix}"
    byte_count = 0
    with path.open("wb") as handle:
        while chunk := await upload.read(1024 * 1024):
            byte_count += len(chunk)
            if byte_count > MAX_FILE_BYTES:
                handle.close()
                path.unlink(missing_ok=True)
                raise ValueError("File vượt giới hạn 25 MB")
            handle.write(chunk)
    await upload.close()
    return path


def create_demo_session(db: Session) -> dict[str, Any]:
    source = Path("data/demo/vn_synthetic_demo")
    if not source.is_dir():
        raise FileNotFoundError("Không tìm thấy dữ liệu demo đã sinh")
    session_id = str(uuid4())
    directory = upload_directory(session_id)
    orders_path = directory / "orders.csv"
    bank_path = directory / "bank.csv"
    shutil.copy2(source / "internal_receivables.csv", orders_path)
    shutil.copy2(source / "bank_transactions.csv", bank_path)
    return _persist_inspection(
        db,
        session_id,
        read_source_bundle(orders_path=orders_path, bank_path=bank_path),
        {"mode": "separate", "orders": str(orders_path), "bank": str(bank_path)},
        mapping=default_demo_mapping(),
        dataset_profile="vn_synthetic_demo",
    )


def create_upload_session(
    db: Session,
    session_id: str,
    raw: RawSourceBundle,
    source_paths: dict[str, Any],
) -> dict[str, Any]:
    return _persist_inspection(db, session_id, raw, source_paths)


def _persist_inspection(
    db: Session,
    session_id: str,
    raw: RawSourceBundle,
    source_paths: dict[str, Any],
    *,
    mapping: MappingConfig | None = None,
    dataset_profile: str = "uploaded",
) -> dict[str, Any]:
    fingerprint = schema_fingerprint(raw)
    matched_profile = db.scalar(
        select(ImportProfile).where(
            ImportProfile.schema_fingerprint == fingerprint,
            ImportProfile.schema_version == SCHEMA_VERSION,
        )
    )
    if not isinstance(matched_profile, ImportProfile):
        matched_profile = None
    profile_reuse_issues: list[str] = []
    if mapping is None and matched_profile is not None:
        profile_input = normalize_bundle(raw, mapping_from_request(matched_profile.mapping_snapshot))
        profile_reuse_issues = sorted(
            {issue.code for issue in profile_input.issues if issue.severity is Severity.BLOCKING}
        )
        if profile_reuse_issues:
            # A schema hash cannot establish that the current values still respect
            # the saved date, money and direction assumptions. Validate all rows.
            matched_profile = None
    effective_mapping = mapping
    if effective_mapping is None and matched_profile is not None:
        effective_mapping = mapping_from_request(matched_profile.mapping_snapshot)
    order_analysis = analyze_mapping(
        raw.orders.frame,
        ORDER_FIELDS,
        feed="orders",
        required_fields=ORDER_REQUIRED,
        profile_mapping=effective_mapping.order_columns if effective_mapping else None,
    )
    bank_analysis = analyze_mapping(
        raw.bank_transactions.frame,
        BANK_FIELDS,
        feed="bank_transactions",
        required_fields=BANK_REQUIRED,
        profile_mapping=effective_mapping.bank_columns if effective_mapping else None,
    )
    # Compatibility response must preserve abstentions from the same analysis;
    # a second alias-only decision path would silently reselect ambiguous columns.
    order_suggestions = order_analysis.selected_mapping
    bank_suggestions = bank_analysis.selected_mapping
    if effective_mapping:
        order_suggestions = effective_mapping.order_columns
        bank_suggestions = effective_mapping.bank_columns
    built_in_profiles = recognize_profiles(raw)
    saved_profile = None
    if matched_profile is not None:
        saved_profile = {
            "id": matched_profile.id,
            "name": matched_profile.name,
            "schema_version": matched_profile.schema_version,
            "mapping_snapshot": matched_profile.mapping_snapshot
            | {
                "import_profile_id": matched_profile.id,
                "import_profile_schema_version": matched_profile.schema_version,
            },
        }
    manifest = {
        "dataset_profile": dataset_profile,
        "schema_fingerprint": fingerprint,
        "schema_version": SCHEMA_VERSION,
        "schema_snapshot": source_schema(raw),
        "recognized_profiles": built_in_profiles,
        "applied_import_profile_id": matched_profile.id if matched_profile is not None else None,
        "source_paths": {
            key: relative_artifact_path(Path(value)) if key in {"orders", "bank", "workbook"} else value
            for key, value in source_paths.items()
        },
        "files": {
            "orders": {
                "name": raw.orders.original_filename,
                "sha256": raw.orders.file_sha256,
                "sheet": raw.orders.sheet_name,
                "structure": to_jsonable(raw.orders.structure),
            },
            "bank": {
                "name": raw.bank_transactions.original_filename,
                "sha256": raw.bank_transactions.file_sha256,
                "sheet": raw.bank_transactions.sheet_name,
                "structure": to_jsonable(raw.bank_transactions.structure),
            },
        },
    }
    session = UploadSession(id=session_id, status="INSPECTED", source_manifest=manifest)
    db.add(session)
    # Explicitly establish the parent row before artifact FKs; the models do not
    # carry ORM relationships because snapshots are queried by their identifiers.
    db.flush()
    for feed, table, path_key in (
        ("RAW_ORDERS", raw.orders, "orders"),
        ("RAW_BANK", raw.bank_transactions, "bank"),
    ):
        relative = manifest["source_paths"].get(path_key) or manifest["source_paths"].get("workbook")
        db.add(
            ArtifactManifest(
                upload_session_id=session_id,
                artifact_type=feed,
                relative_path=relative,
                sha256=table.file_sha256,
                byte_size=resolve_artifact_path(relative).stat().st_size,
            )
        )
    db.commit()
    return {
        "session_id": session_id,
        "status": session.status,
        "dataset_profile": dataset_profile,
        "raw_eda": {
            "orders": eda_to_dict(summarize_raw(raw.orders)),
            "bank_transactions": eda_to_dict(summarize_raw(raw.bank_transactions)),
        },
        "suggested_mapping": {
            "order_columns": order_suggestions,
            "bank_columns": bank_suggestions,
        },
        "mapping_suggestions": {
            "orders": to_jsonable(order_analysis),
            "bank_transactions": to_jsonable(bank_analysis),
        },
        "detected_structure": {
            "orders": to_jsonable(raw.orders.structure),
            "bank_transactions": to_jsonable(raw.bank_transactions.structure),
        },
        "import_profile": {
            "schema_fingerprint": fingerprint,
            "schema_version": SCHEMA_VERSION,
            "recognized": built_in_profiles,
            "saved_profile": saved_profile,
            "applied": matched_profile is not None,
            "reuse_issue_codes": profile_reuse_issues,
        },
    }


def mapping_from_request(request: MappingRequest | dict[str, Any]) -> MappingConfig:
    validated = request if isinstance(request, MappingRequest) else MappingRequest.model_validate(request)
    payload = validated.model_dump()
    return MappingConfig(**payload)


def load_raw_bundle(session: UploadSession) -> RawSourceBundle:
    paths = session.source_manifest["source_paths"]
    files = session.source_manifest.get("files", {})
    order_structure = files.get("orders", {}).get("structure", {}).get("selected", {})
    bank_structure = files.get("bank", {}).get("structure", {}).get("selected", {})
    if paths["mode"] == "workbook":
        return read_source_bundle(
            workbook_path=resolve_artifact_path(paths["workbook"]),
            orders_sheet=order_structure.get("sheet_name") or paths.get("orders_sheet"),
            bank_sheet=bank_structure.get("sheet_name") or paths.get("bank_sheet"),
            orders_header_row=order_structure.get("header_row_number"),
            bank_header_row=bank_structure.get("header_row_number"),
            orders_header_depth=order_structure.get("header_depth"),
            bank_header_depth=bank_structure.get("header_depth"),
        )
    return read_source_bundle(
        orders_path=resolve_artifact_path(paths["orders"]),
        bank_path=resolve_artifact_path(paths["bank"]),
        orders_header_row=order_structure.get("header_row_number"),
        bank_header_row=bank_structure.get("header_row_number"),
        orders_header_depth=order_structure.get("header_depth"),
        bank_header_depth=bank_structure.get("header_depth"),
        orders_delimiter=order_structure.get("delimiter"),
        bank_delimiter=bank_structure.get("delimiter"),
    )


def read_source_rows(
    session: UploadSession,
    feed: str,
    row_numbers: list[int],
    *,
    limit: int = 50,
) -> dict[int, dict[str, Any]]:
    """Read selected rows through the same structure-aware reader used for normalization."""
    if feed not in {"orders", "bank_transactions"}:
        raise ValueError("Nguồn dữ liệu không hợp lệ")
    targets = sorted({number for number in row_numbers if number >= 2})
    if len(targets) > limit:
        raise ValueError(f"Chỉ được đọc tối đa {limit} dòng nguồn mỗi yêu cầu")
    if not targets:
        return {}
    raw = load_raw_bundle(session)
    table = raw.orders if feed == "orders" else raw.bank_transactions
    positions = {row_number: index for index, row_number in enumerate(table.source_row_numbers)}
    return {
        row_number: {
            str(key): "" if value is None else str(value)
            for key, value in table.frame.iloc[positions[row_number]].items()
        }
        for row_number in targets
        if row_number in positions
    }


def confirm_mapping(db: Session, session: UploadSession, request: MappingRequest) -> dict[str, Any]:
    mapping = mapping_from_request(request)
    raw = load_raw_bundle(session)
    if mapping.import_profile_id:
        profile = db.get(ImportProfile, mapping.import_profile_id)
        if profile is None:
            raise ValueError("Import profile không tồn tại")
        if (
            mapping.import_profile_schema_version != profile.schema_version
            or profile.schema_version != SCHEMA_VERSION
            or profile.schema_fingerprint != schema_fingerprint(raw)
        ):
            raise ValueError("Import profile không còn khớp cấu trúc nguồn hiện tại")
    if not mapping.confirmed_structure and any(
        table.structure.status == "NEEDS_REVIEW" for table in (raw.orders, raw.bank_transactions)
    ):
        raise ValueError("Cấu trúc file có nhiều cách diễn giải; cần xác nhận sheet và hàng tiêu đề.")
    normalized = normalize_bundle(raw, mapping)
    report = build_health_report(normalized)
    standardized = summarize_standardized(
        list(normalized.orders), list(normalized.bank_transactions), mapping.currency.value
    )
    session.mapping_snapshot = to_jsonable(mapping)
    session.health_snapshot = {
        "report": to_jsonable(report),
        "exclusions": [],
        "acknowledged_issue_codes": [],
        "standardized_eda": eda_to_dict(standardized),
        "issue_details": _health_issue_details(raw, normalized, report, session.source_manifest),
    }
    session.status = "HEALTH_READY" if report.status == "READY" else "HEALTH_BLOCKED"
    db.commit()
    return session.health_snapshot | {"session_id": session.id, "status": session.status}


def preview_mapping(session: UploadSession, request: MappingRequest, *, limit: int = 10) -> dict[str, Any]:
    """Normalize a bounded preview without mutating the upload session."""
    mapping = mapping_from_request(request)
    raw = load_raw_bundle(session)
    normalized = normalize_bundle(raw, mapping)
    report = build_health_report(normalized)
    standardized = summarize_standardized(
        list(normalized.orders), list(normalized.bank_transactions), mapping.currency.value
    )
    return {
        "session_id": session.id,
        "status": report.status,
        "orders": [to_jsonable(order) for order in normalized.orders[:limit]],
        "bank_transactions": [to_jsonable(bank) for bank in normalized.bank_transactions[:limit]],
        "issues": [to_jsonable(issue) for issue in report.issues[:limit]],
        "blocking_count": report.blocking_count,
        "warning_count": report.warning_count,
        "standardized_eda": eda_to_dict(standardized),
        "preview_limit": limit,
    }


def normalized_csv(session: UploadSession, feed: str) -> str:
    """Serialize confirmed canonical rows only after the Health Gate is ready."""
    if session.status != "HEALTH_READY" or not session.mapping_snapshot:
        raise ValueError("Chỉ tải dữ liệu chuẩn hóa sau khi Health Gate sẵn sàng")
    normalized, report = normalize_session(session)
    if report.status != "READY":
        raise ValueError("Dữ liệu còn lỗi chặn chưa được giải quyết")
    if feed == "orders":
        records = [asdict(row) for row in normalized.orders]
    elif feed == "bank_transactions":
        records = [asdict(row) for row in normalized.bank_transactions]
    else:
        raise ValueError("Feed chuẩn hóa không hợp lệ")
    flattened: list[dict[str, Any]] = []
    for record in records:
        lineage = record.pop("lineage", None) or {}
        flattened.append(
            {
                **to_jsonable(record),
                "source_file_id": lineage.get("source_file_id"),
                "source_row_number": lineage.get("source_row_number"),
                "source_row_hash": lineage.get("source_row_hash"),
            }
        )
    if not flattened:
        return ""
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(flattened[0]))
    writer.writeheader()
    writer.writerows(flattened)
    return output.getvalue()


def normalize_session(session: UploadSession) -> tuple[NormalizedBundle, Any]:
    if not session.mapping_snapshot:
        raise ValueError("Mapping chưa được xác nhận")
    normalized = normalize_bundle(load_raw_bundle(session), mapping_from_request(session.mapping_snapshot))
    exclusions = [Exclusion(**item) for item in (session.health_snapshot or {}).get("exclusions", [])]
    if exclusions:
        return apply_exclusions(normalized, exclusions)
    return normalized, build_health_report(normalized)


def apply_resolution(db: Session, session: UploadSession, request: ResolutionRequest) -> dict[str, Any]:
    raw = load_raw_bundle(session)
    normalized = normalize_bundle(raw, mapping_from_request(session.mapping_snapshot or {}))
    valid_rows = {
        "orders": set(raw.orders.source_row_numbers),
        "bank_transactions": set(raw.bank_transactions.source_row_numbers),
    }
    for exclusion in request.exclusions:
        if exclusion.source_row_number not in valid_rows[exclusion.feed]:
            raise ValueError(f"Dòng {exclusion.source_row_number} không tồn tại trong nguồn {exclusion.feed}")
    exclusions = [Exclusion(**item.model_dump()) for item in request.exclusions]
    resolved, report = apply_exclusions(normalized, exclusions)
    mapping = mapping_from_request(session.mapping_snapshot or {})
    standardized = summarize_standardized(
        list(resolved.orders), list(resolved.bank_transactions), mapping.currency.value
    )
    session.health_snapshot = {
        "report": to_jsonable(report),
        "exclusions": to_jsonable(exclusions),
        "acknowledged_issue_codes": sorted(set(request.acknowledged_issue_codes)),
        "standardized_eda": eda_to_dict(standardized),
        "issue_details": _health_issue_details(raw, resolved, report, session.source_manifest),
    }
    session.status = "HEALTH_READY" if report.status == "READY" else "HEALTH_BLOCKED"
    db.commit()
    return session.health_snapshot | {"session_id": session.id, "status": session.status}


def health_issue_detail(session: UploadSession, issue_index: int) -> dict[str, Any]:
    """Return a bounded detail snapshot produced during mapping, never an arbitrary file path."""
    details = (session.health_snapshot or {}).get("issue_details", [])
    if issue_index < 0 or issue_index >= len(details):
        raise LookupError("HEALTH_ISSUE_NOT_FOUND")
    return details[issue_index]


def _health_issue_details(
    raw: RawSourceBundle,
    normalized: NormalizedBundle,
    report: Any,
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    """Persist at most 50 related rows per issue while the full mapping pass is already in memory."""
    canonical_by_row: dict[tuple[str, int], dict[str, Any]] = {}
    for feed, records in (("orders", normalized.orders), ("bank_transactions", normalized.bank_transactions)):
        for record in records:
            if record.lineage:
                canonical_by_row[(feed, record.lineage.source_row_number)] = to_jsonable(asdict(record))

    file_meta = manifest.get("files", {})
    tables = {"orders": raw.orders, "bank_transactions": raw.bank_transactions}
    actions = {
        "POSSIBLE_REIMPORT": (
            "So sánh hai dòng nguồn và mã giao dịch; chỉ loại trừ khi xác minh đây là cùng một giao dịch nhập lặp."
        ),
        "MISSING_REFERENCE_EVIDENCE": (
            "Bổ sung mã tham chiếu hoặc nội dung giao dịch nếu nguồn có dữ liệu; "
            "nếu không, giao dịch chỉ được đề xuất ghép."
        ),
        "ORDER_ID_COLLISION": "Sửa mã đơn hàng hoặc cấu hình khóa ghép có thể phân biệt từng nghĩa vụ.",
        "BANK_ID_COLLISION": "Sửa mã giao dịch bị trùng trước khi chạy đối soát.",
        "ORDER_PARSE_ERROR": "Sửa giá trị sai định dạng trong file nguồn hoặc loại trừ dòng kèm lý do nghiệp vụ.",
        "BANK_PARSE_ERROR": "Sửa giá trị sai định dạng trong file nguồn hoặc loại trừ dòng kèm lý do nghiệp vụ.",
        "CURRENCY_MISMATCH": "Tách dữ liệu theo loại tiền hoặc sửa cột loại tiền đã ghép.",
    }
    details: list[dict[str, Any]] = []
    for issue_index, issue in enumerate(report.issues):
        table = tables.get(issue.feed)
        rows: list[dict[str, Any]] = []
        for row_number in issue.source_rows[:50]:
            raw_values: dict[str, Any] = {}
            if table is not None and row_number in table.source_row_numbers:
                position = table.source_row_numbers.index(row_number)
                raw_values = {
                    str(key): str(value) if value is not None else ""
                    for key, value in table.frame.iloc[position].items()
                }
            normalized_values = canonical_by_row.get((issue.feed, row_number))
            rows.append(
                {
                    "source_row_number": row_number,
                    "source_filename": file_meta.get("orders" if issue.feed == "orders" else "bank", {}).get("name"),
                    "sheet_name": table.sheet_name if table is not None else None,
                    "raw_values": raw_values,
                    "normalized_values": normalized_values,
                    "source_row_hash": (normalized_values or {}).get("lineage", {}).get("source_row_hash"),
                }
            )
        details.append(
            {
                "issue_index": issue_index,
                "code": issue.code,
                "severity": issue.severity.value,
                "feed": issue.feed,
                "message_vi": issue.message_vi,
                "sample_values": list(issue.sample_values),
                "suggested_action_vi": actions.get(
                    issue.code,
                    "Kiểm tra dữ liệu nguồn và cách ghép cột; việc xem chi tiết không thay đổi dữ liệu.",
                ),
                "rows": rows,
                "row_count": len(issue.source_rows),
                "is_truncated": len(issue.source_rows) > 50,
            }
        )
    return details
