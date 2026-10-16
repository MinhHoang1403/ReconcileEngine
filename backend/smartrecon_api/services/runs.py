"""Reconciliation execution, PostgreSQL snapshots, and artifact persistence."""

from __future__ import annotations

from datetime import UTC, date, datetime
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
    VerifiedAdjustmentRecord,
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
from smartrecon.domain.invariants import ConservationReport
from smartrecon.domain.models import (
    AllocationEdge,
    BankTransaction,
    Candidate,
    ExceptionCase,
    MatchEvidence,
    MatchGroup,
    Order,
    SourceLineage,
    VerifiedAdjustment,
)
from smartrecon.domain.statuses import (
    AmountBasis,
    Currency,
    Direction,
    GroupType,
    LinkStatus,
    OrderStatus,
    PaymentStatus,
    ReviewStatus,
)
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
            parent_revision=None,
            action_id=None,
            effective_checksum=hash_json(result_payload),
            result_artifact_path=relative_artifact_path(result_path),
            summary=result.kpis,
        )
    )
    persist_effective_records(db, run_id, 0, result)
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


def result_from_payload(payload: dict[str, Any]) -> ReconciliationResult:
    """Restore typed core records from a trusted run-scoped JSON snapshot."""

    def lineage(value: dict[str, Any] | None) -> SourceLineage | None:
        return SourceLineage(**value) if value else None

    def evidence(value: dict[str, Any]) -> MatchEvidence:
        return MatchEvidence(
            rule_id=value["rule_id"],
            rule_version=value["rule_version"],
            reason_codes=tuple(value["reason_codes"]),
            explanation_vi=value["explanation_vi"],
            reference_hits=tuple(value.get("reference_hits", ())),
            amount_delta_minor=value.get("amount_delta_minor"),
            date_delta_days=value.get("date_delta_days"),
            score=value.get("score"),
            features=value.get("features", {}),
        )

    orders = tuple(
        Order(
            order_id=item["order_id"],
            ordered_at=date.fromisoformat(item["ordered_at"]),
            expected_amount_minor=item["expected_amount_minor"],
            currency=Currency(item["currency"]),
            order_status=OrderStatus(item["order_status"]),
            external_ref=item.get("external_ref"),
            customer_id=item.get("customer_id"),
            customer_name=item.get("customer_name"),
            payment_channel=item.get("payment_channel"),
            batch_ref=item.get("batch_ref"),
            description=item.get("description"),
            lineage=lineage(item.get("lineage")),
        )
        for item in payload["orders"]
    )
    banks = tuple(
        BankTransaction(
            bank_txn_id=item["bank_txn_id"],
            txn_date=date.fromisoformat(item["txn_date"]),
            posted_amount_minor=item["posted_amount_minor"],
            direction=Direction(item["direction"]),
            amount_basis=AmountBasis(item["amount_basis"]),
            currency=Currency(item["currency"]),
            txn_ref=item.get("txn_ref"),
            value_date=date.fromisoformat(item["value_date"]) if item.get("value_date") else None,
            description=item.get("description"),
            sender_name=item.get("sender_name"),
            channel=item.get("channel"),
            batch_ref=item.get("batch_ref"),
            declared_fee_minor=item.get("declared_fee_minor"),
            lineage=lineage(item.get("lineage")),
        )
        for item in payload["bank_transactions"]
    )
    groups = tuple(
        MatchGroup(
            group_id=item["group_id"],
            group_type=GroupType(item["group_type"]),
            order_ids=tuple(item["order_ids"]),
            bank_txn_ids=tuple(item["bank_txn_ids"]),
            link_status=LinkStatus(item["link_status"]),
            review_status=ReviewStatus(item["review_status"]),
            payment_statuses={key: PaymentStatus(value) for key, value in item["payment_statuses"].items()},
            evidence=evidence(item["evidence"]),
        )
        for item in payload["groups"]
    )
    allocations = tuple(
        AllocationEdge(
            edge_id=item["edge_id"],
            group_id=item["group_id"],
            order_id=item["order_id"],
            bank_txn_id=item["bank_txn_id"],
            allocated_cash_minor=item["allocated_cash_minor"],
            currency=Currency(item["currency"]),
        )
        for item in payload["allocations"]
    )
    adjustments = tuple(VerifiedAdjustment(**item) for item in payload["adjustments"])
    candidates = tuple(
        Candidate(
            candidate_id=item["candidate_id"],
            order_ids=tuple(item["order_ids"]),
            bank_txn_ids=tuple(item["bank_txn_ids"]),
            group_type=GroupType(item["group_type"]),
            evidence=evidence(item["evidence"]),
            competing_candidate_ids=tuple(item.get("competing_candidate_ids", ())),
        )
        for item in payload["candidates"]
    )
    exceptions = tuple(
        ExceptionCase(
            exception_id=item["exception_id"],
            reason_codes=tuple(item["reason_codes"]),
            order_ids=tuple(item.get("order_ids", ())),
            bank_txn_ids=tuple(item.get("bank_txn_ids", ())),
            risk_amount_minor=item.get("risk_amount_minor", 0),
        )
        for item in payload["exceptions"]
    )
    conservation_payload = payload["conservation"]
    conservation = ConservationReport(
        bank_allocated=conservation_payload["bank_allocated"],
        bank_unapplied=conservation_payload["bank_unapplied"],
        order_allocated=conservation_payload["order_allocated"],
        order_adjusted=conservation_payload["order_adjusted"],
        order_outstanding=conservation_payload["order_outstanding"],
        violations=tuple(conservation_payload["violations"]),
    )
    return ReconciliationResult(
        orders=orders,
        bank_transactions=banks,
        groups=groups,
        allocations=allocations,
        adjustments=adjustments,
        candidates=candidates,
        exceptions=exceptions,
        payment_statuses={key: PaymentStatus(value) for key, value in payload["payment_statuses"].items()},
        bank_unapplied_minor=payload["bank_unapplied_minor"],
        order_outstanding_minor=payload["order_outstanding_minor"],
        kpis=payload["kpis"],
        layer_counts=payload["layer_counts"],
        conservation=conservation,
        semantic_checksum=payload["semantic_checksum"],
    )


def effective_result_path(run_id: str, revision: int) -> Path:
    """Return the immutable result artifact path for one revision, including legacy revision zero."""
    if revision == 0:
        return run_directory(run_id) / "result.json"
    return run_directory(run_id) / "revisions" / str(revision) / "result.json"


def write_effective_result(run_id: str, revision: int, result: ReconciliationResult) -> tuple[Path, dict[str, Any]]:
    """Atomically write an immutable revision payload before it can be published in PostgreSQL."""
    payload = result_to_payload(result)
    path = effective_result_path(run_id, revision)
    write_json(path, payload)
    return path, payload


def load_run_result(run_id: str, revision: int = 0) -> dict[str, Any]:
    return read_json(effective_result_path(run_id, revision))


def persist_effective_records(
    db: Session,
    run_id: str,
    revision: int,
    result: ReconciliationResult,
) -> None:
    """Persist group, cash-edge, and adjustment snapshots for one immutable revision."""
    for group in result.groups:
        db.add(
            MatchGroupRecord(
                run_id=run_id,
                revision=revision,
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
                revision=revision,
                edge_id=edge.edge_id,
                group_id=edge.group_id,
                order_id=edge.order_id,
                bank_txn_id=edge.bank_txn_id,
                allocated_cash_minor=edge.allocated_cash_minor,
                currency=edge.currency.value,
            )
        )
    for adjustment in result.adjustments:
        db.add(
            VerifiedAdjustmentRecord(
                run_id=run_id,
                revision=revision,
                adjustment_id=adjustment.adjustment_id,
                order_id=adjustment.order_id,
                amount_minor=adjustment.amount_minor,
                adjustment_type=adjustment.adjustment_type,
                evidence_reference=adjustment.evidence_reference,
            )
        )


def paginate(items: list[Any], page: int, page_size: int) -> dict[str, Any]:
    start = (page - 1) * page_size
    return {
        "items": items[start : start + page_size],
        "page": page,
        "page_size": page_size,
        "total": len(items),
    }
