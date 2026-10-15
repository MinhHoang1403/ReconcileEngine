"""Reconciliation execution, PostgreSQL snapshots, and artifact persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from sqlalchemy.orm import Session

from backend.smartrecon_api.db.models import (
    AllocationEdgeRecord,
    ArtifactManifest,
    MatchGroupRecord,
    ReconciliationRun,
    RunRevision,
    UploadSession,
)
from backend.smartrecon_api.schemas.runs import RunRequest
from backend.smartrecon_api.services.artifacts import (
    relative_artifact_path,
    run_directory,
    sha256_path,
)
from backend.smartrecon_api.services.serialization import hash_json, read_json, to_jsonable, write_json
from backend.smartrecon_api.services.uploads import normalize_session
from smartrecon.config import ReconciliationPolicy
from smartrecon.engine import ReconciliationResult, run_reconciliation


def policy_from_request(request: RunRequest) -> ReconciliationPolicy:
    return ReconciliationPolicy(**request.policy.model_dump())


def execute_run(db: Session, session: UploadSession, request: RunRequest) -> ReconciliationRun:
    normalized, health = normalize_session(session)
    if health.status != "READY":
        raise ValueError("HEALTH_BLOCKED")
    policy = policy_from_request(request)
    result = run_reconciliation(normalized, policy)
    run_id = str(uuid4())
    directory = run_directory(run_id)
    result_payload = result_to_payload(result)
    mapping_snapshot = session.mapping_snapshot or {}
    policy_snapshot = to_jsonable(policy)
    run_manifest = {
        "run_id": run_id,
        "effective_revision": 0,
        "input_hashes": normalized.source_hashes,
        "mapping_hash": hash_json(mapping_snapshot),
        "policy_hash": hash_json(policy_snapshot),
        "rule_version": policy.rule_version,
        "semantic_checksum": result.semantic_checksum,
    }

    result_path = directory / "result.json"
    manifest_path = directory / "run_manifest.json"
    orders_path = directory / "canonical_orders.parquet"
    bank_path = directory / "canonical_bank.parquet"
    write_json(result_path, result_payload)
    write_json(manifest_path, run_manifest)
    _write_parquet(orders_path, result_payload["orders"])
    _write_parquet(bank_path, result_payload["bank_transactions"])

    run = ReconciliationRun(
        id=run_id,
        upload_session_id=session.id,
        status="COMPLETED",
        currency=policy.currency.value,
        policy_snapshot=policy_snapshot,
        mapping_snapshot=mapping_snapshot,
        semantic_checksum=result.semantic_checksum,
        current_revision=0,
        completed_at=datetime.now(UTC),
    )
    db.add(run)
    db.flush()
    db.add(
        RunRevision(
            run_id=run_id,
            revision=0,
            effective_checksum=result.semantic_checksum,
            summary=result.kpis,
        )
    )
    for group in result.groups:
        db.add(
            MatchGroupRecord(
                run_id=run_id,
                revision=0,
                group_id=group.group_id,
                group_type=group.group_type.value,
                link_status=group.link_status.value,
                review_status=group.review_status.value,
                evidence=to_jsonable(group),
            )
        )
    for edge in result.allocations:
        db.add(
            AllocationEdgeRecord(
                run_id=run_id,
                revision=0,
                edge_id=edge.edge_id,
                group_id=edge.group_id,
                order_id=edge.order_id,
                bank_txn_id=edge.bank_txn_id,
                allocated_cash_minor=edge.allocated_cash_minor,
                currency=edge.currency.value,
            )
        )
    for artifact_type, path in (
        ("RESULT", result_path),
        ("RUN_MANIFEST", manifest_path),
        ("CANONICAL_ORDERS", orders_path),
        ("CANONICAL_BANK", bank_path),
    ):
        db.add(
            ArtifactManifest(
                run_id=run_id,
                artifact_type=artifact_type,
                relative_path=relative_artifact_path(path),
                sha256=sha256_path(path),
                byte_size=path.stat().st_size,
            )
        )
    db.commit()
    db.refresh(run)
    return run


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    flattened = []
    for row in rows:
        item = dict(row)
        lineage = item.pop("lineage", None) or {}
        item.update({f"source_{key}": value for key, value in lineage.items()})
        flattened.append(item)
    pd.DataFrame(flattened).to_parquet(path, index=False)


def result_to_payload(result: ReconciliationResult) -> dict[str, Any]:
    conservation = to_jsonable(result.conservation)
    conservation["is_valid"] = result.conservation.is_valid
    return {
        "orders": to_jsonable(result.orders),
        "bank_transactions": to_jsonable(result.bank_transactions),
        "groups": to_jsonable(result.groups),
        "allocations": to_jsonable(result.allocations),
        "adjustments": to_jsonable(result.adjustments),
        "candidates": to_jsonable(result.candidates),
        "exceptions": to_jsonable(result.exceptions),
        "payment_statuses": to_jsonable(result.payment_statuses),
        "bank_unapplied_minor": result.bank_unapplied_minor,
        "order_outstanding_minor": result.order_outstanding_minor,
        "kpis": result.kpis,
        "layer_counts": result.layer_counts,
        "semantic_checksum": result.semantic_checksum,
        "conservation": conservation,
    }


def load_run_result(run_id: str) -> dict[str, Any]:
    return read_json(run_directory(run_id) / "result.json")


def paginate(items: list[Any], page: int, page_size: int) -> dict[str, Any]:
    start = (page - 1) * page_size
    return {
        "items": items[start : start + page_size],
        "page": page,
        "page_size": page_size,
        "total": len(items),
    }
