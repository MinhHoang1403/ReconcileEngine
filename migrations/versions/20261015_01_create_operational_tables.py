"""Create operational upload, run, result, and artifact tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261015_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial PostgreSQL schema."""
    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_manifest", sa.JSON(), nullable=False),
        sa.Column("mapping_snapshot", sa.JSON(), nullable=True),
        sa.Column("health_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("upload_session_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("policy_snapshot", sa.JSON(), nullable=False),
        sa.Column("mapping_snapshot", sa.JSON(), nullable=False),
        sa.Column("semantic_checksum", sa.String(length=64), nullable=True),
        sa.Column("current_revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["upload_session_id"], ["upload_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("semantic_checksum"),
    )
    op.create_index("ix_runs_upload_session_id", "runs", ["upload_session_id"])
    op.create_table(
        "run_revisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("effective_checksum", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "revision", name="uq_run_revision"),
    )
    op.create_index("ix_run_revisions_run_id", "run_revisions", ["run_id"])
    op.create_table(
        "review_actions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("revision_before", sa.Integer(), nullable=False),
        sa.Column("revision_after", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_actions_run_id", "review_actions", ["run_id"])
    op.create_table(
        "match_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.String(length=64), nullable=False),
        sa.Column("group_type", sa.String(length=40), nullable=False),
        sa.Column("link_status", sa.String(length=24), nullable=False),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "revision", "group_id", name="uq_group_snapshot"),
    )
    op.create_index("ix_match_groups_run_id", "match_groups", ["run_id"])
    op.create_table(
        "allocation_edges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("edge_id", sa.String(length=64), nullable=False),
        sa.Column("group_id", sa.String(length=64), nullable=False),
        sa.Column("order_id", sa.String(length=160), nullable=False),
        sa.Column("bank_txn_id", sa.String(length=160), nullable=False),
        sa.Column("allocated_cash_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "revision", "edge_id", name="uq_edge_snapshot"),
    )
    op.create_index("ix_allocation_edges_run_id", "allocation_edges", ["run_id"])
    op.create_index("ix_allocation_edges_order_id", "allocation_edges", ["order_id"])
    op.create_index("ix_allocation_edges_bank_txn_id", "allocation_edges", ["bank_txn_id"])
    op.create_table(
        "artifact_manifest",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("upload_session_id", sa.String(length=36), nullable=True),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("relative_path", sa.String(length=500), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["upload_session_id"], ["upload_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_artifact_manifest_run_id", "artifact_manifest", ["run_id"])
    op.create_index("ix_artifact_manifest_upload_session_id", "artifact_manifest", ["upload_session_id"])


def downgrade() -> None:
    """Remove all initial operational tables in reverse dependency order."""
    op.drop_table("artifact_manifest")
    op.drop_table("allocation_edges")
    op.drop_table("match_groups")
    op.drop_table("review_actions")
    op.drop_table("run_revisions")
    op.drop_table("runs")
    op.drop_table("upload_sessions")
