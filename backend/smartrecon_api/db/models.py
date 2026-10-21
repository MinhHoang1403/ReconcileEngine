"""Operational PostgreSQL models for uploads, runs, and immutable results."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.smartrecon_api.db.database import Base


class UploadSession(Base):
    """Metadata for two immutable input feeds before reconciliation."""

    __tablename__ = "upload_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="UPLOADED")
    source_manifest: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    mapping_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    health_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportProfile(Base):
    """User-confirmed import configuration bound to one exact two-feed schema."""

    __tablename__ = "import_profiles"
    __table_args__ = (UniqueConstraint("schema_fingerprint"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    schema_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    mapping_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReconciliationRun(Base):
    """An immutable input/config reconciliation execution."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    upload_session_id: Mapped[str] = mapped_column(ForeignKey("upload_sessions.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    mapping_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    semantic_checksum: Mapped[str | None] = mapped_column(String(64), index=True)
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunRevision(Base):
    """Effective immutable snapshot metadata for a run."""

    __tablename__ = "run_revisions"
    __table_args__ = (UniqueConstraint("run_id", "revision", name="uq_run_revision"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_revision: Mapped[int | None] = mapped_column(Integer)
    action_id: Mapped[str | None] = mapped_column(String(36))
    effective_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    result_artifact_path: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewAction(Base):
    """Immutable audit record for one committed manual review command."""

    __tablename__ = "review_actions"
    __table_args__ = (UniqueConstraint("run_id", "idempotency_key", name="uq_review_action_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    revision_before: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_after: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(120))
    command_hash: Mapped[str | None] = mapped_column(String(64))
    target_group_id: Mapped[str | None] = mapped_column(String(64))
    actor_label: Mapped[str | None] = mapped_column(String(120))
    undo_of_action_id: Mapped[str | None] = mapped_column(String(36))
    note: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MatchGroupRecord(Base):
    """Persisted group snapshot for one effective run revision."""

    __tablename__ = "match_groups"
    __table_args__ = (UniqueConstraint("run_id", "revision", "group_id", name="uq_group_snapshot"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    group_id: Mapped[str] = mapped_column(String(64), nullable=False)
    group_type: Mapped[str] = mapped_column(String(40), nullable=False)
    link_status: Mapped[str] = mapped_column(String(24), nullable=False)
    review_status: Mapped[str] = mapped_column(String(24), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class AllocationEdgeRecord(Base):
    """Confirmed cash assigned from one bank row to one receivable."""

    __tablename__ = "allocation_edges"
    __table_args__ = (UniqueConstraint("run_id", "revision", "edge_id", name="uq_edge_snapshot"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    edge_id: Mapped[str] = mapped_column(String(64), nullable=False)
    group_id: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    bank_txn_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    allocated_cash_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)


class VerifiedAdjustmentRecord(Base):
    """Non-cash adjustments in one immutable effective revision."""

    __tablename__ = "verified_adjustments"
    __table_args__ = (UniqueConstraint("run_id", "revision", "adjustment_id", name="uq_adjustment_snapshot"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    adjustment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    adjustment_type: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_reference: Mapped[str] = mapped_column(String(500), nullable=False)


class ArtifactManifest(Base):
    """Checksummed file artifact belonging to an upload or run."""

    __tablename__ = "artifact_manifest"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    upload_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("upload_sessions.id", ondelete="CASCADE"), index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(40), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
