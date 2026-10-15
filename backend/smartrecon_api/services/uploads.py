"""Upload persistence, inspection, mapping, and Health Gate orchestration."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.smartrecon_api.db.models import ArtifactManifest, UploadSession
from backend.smartrecon_api.schemas.uploads import MappingRequest, ResolutionRequest
from backend.smartrecon_api.services.artifacts import (
    relative_artifact_path,
    resolve_artifact_path,
    upload_directory,
)
from backend.smartrecon_api.services.serialization import to_jsonable
from smartrecon.ingest.eda import eda_to_dict, summarize_raw, summarize_standardized
from smartrecon.ingest.health import Exclusion, apply_exclusions, build_health_report
from smartrecon.ingest.mapping import (
    BANK_REQUIRED,
    ORDER_REQUIRED,
    MappingConfig,
    default_demo_mapping,
    suggest_mapping,
)
from smartrecon.ingest.normalization import NormalizedBundle, normalize_bundle
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
    order_suggestions = suggest_mapping(
        list(raw.orders.frame.columns),
        ORDER_REQUIRED
        | {"currency", "order_status", "external_ref", "customer_name", "payment_channel", "description"},
    )
    bank_suggestions = suggest_mapping(
        list(raw.bank_transactions.frame.columns),
        BANK_REQUIRED
        | {"currency", "txn_ref", "value_date", "description", "sender_name", "channel", "batch_ref", "declared_fee"},
    )
    if mapping:
        order_suggestions = mapping.order_columns
        bank_suggestions = mapping.bank_columns
    manifest = {
        "dataset_profile": dataset_profile,
        "source_paths": {
            key: relative_artifact_path(Path(value)) if key in {"orders", "bank", "workbook"} else value
            for key, value in source_paths.items()
        },
        "files": {
            "orders": {
                "name": raw.orders.original_filename,
                "sha256": raw.orders.file_sha256,
                "sheet": raw.orders.sheet_name,
            },
            "bank": {
                "name": raw.bank_transactions.original_filename,
                "sha256": raw.bank_transactions.file_sha256,
                "sheet": raw.bank_transactions.sheet_name,
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
    }


def mapping_from_request(request: MappingRequest | dict[str, Any]) -> MappingConfig:
    validated = request if isinstance(request, MappingRequest) else MappingRequest.model_validate(request)
    payload = validated.model_dump()
    return MappingConfig(**payload)


def load_raw_bundle(session: UploadSession) -> RawSourceBundle:
    paths = session.source_manifest["source_paths"]
    if paths["mode"] == "workbook":
        return read_source_bundle(
            workbook_path=resolve_artifact_path(paths["workbook"]),
            orders_sheet=paths["orders_sheet"],
            bank_sheet=paths["bank_sheet"],
        )
    return read_source_bundle(
        orders_path=resolve_artifact_path(paths["orders"]),
        bank_path=resolve_artifact_path(paths["bank"]),
    )


def confirm_mapping(db: Session, session: UploadSession, request: MappingRequest) -> dict[str, Any]:
    mapping = mapping_from_request(request)
    normalized = normalize_bundle(load_raw_bundle(session), mapping)
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
    }
    session.status = "HEALTH_READY" if report.status == "READY" else "HEALTH_BLOCKED"
    db.commit()
    return session.health_snapshot | {"session_id": session.id, "status": session.status}


def normalize_session(session: UploadSession) -> tuple[NormalizedBundle, Any]:
    if not session.mapping_snapshot:
        raise ValueError("Mapping chưa được xác nhận")
    normalized = normalize_bundle(load_raw_bundle(session), mapping_from_request(session.mapping_snapshot))
    exclusions = [Exclusion(**item) for item in (session.health_snapshot or {}).get("exclusions", [])]
    if exclusions:
        return apply_exclusions(normalized, exclusions)
    return normalized, build_health_report(normalized)


def apply_resolution(db: Session, session: UploadSession, request: ResolutionRequest) -> dict[str, Any]:
    normalized = normalize_bundle(load_raw_bundle(session), mapping_from_request(session.mapping_snapshot or {}))
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
    }
    session.status = "HEALTH_READY" if report.status == "READY" else "HEALTH_BLOCKED"
    db.commit()
    return session.health_snapshot | {"session_id": session.id, "status": session.status}
