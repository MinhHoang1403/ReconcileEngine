"""Add transactional review metadata and adjustment snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261015_03"
down_revision: str | None = "20261015_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Extend existing review tables without rewriting historical revision zero rows."""
    op.add_column("run_revisions", sa.Column("parent_revision", sa.Integer(), nullable=True))
    op.add_column("run_revisions", sa.Column("action_id", sa.String(length=36), nullable=True))
    op.add_column("run_revisions", sa.Column("result_artifact_path", sa.String(length=500), nullable=True))

    op.add_column("review_actions", sa.Column("idempotency_key", sa.String(length=120), nullable=True))
    op.add_column("review_actions", sa.Column("command_hash", sa.String(length=64), nullable=True))
    op.add_column("review_actions", sa.Column("target_group_id", sa.String(length=64), nullable=True))
    op.add_column("review_actions", sa.Column("actor_label", sa.String(length=120), nullable=True))
    op.add_column("review_actions", sa.Column("undo_of_action_id", sa.String(length=36), nullable=True))
    op.create_unique_constraint(
        "uq_review_action_idempotency",
        "review_actions",
        ["run_id", "idempotency_key"],
    )

    op.create_table(
        "verified_adjustments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("adjustment_id", sa.String(length=64), nullable=False),
        sa.Column("order_id", sa.String(length=160), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("adjustment_type", sa.String(length=40), nullable=False),
        sa.Column("evidence_reference", sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "revision", "adjustment_id", name="uq_adjustment_snapshot"),
    )
    op.create_index("ix_verified_adjustments_run_id", "verified_adjustments", ["run_id"])
    op.create_index("ix_verified_adjustments_order_id", "verified_adjustments", ["order_id"])


def downgrade() -> None:
    """Remove review extensions while preserving the original operational schema."""
    op.drop_table("verified_adjustments")
    op.drop_constraint("uq_review_action_idempotency", "review_actions", type_="unique")
    op.drop_column("review_actions", "undo_of_action_id")
    op.drop_column("review_actions", "actor_label")
    op.drop_column("review_actions", "target_group_id")
    op.drop_column("review_actions", "command_hash")
    op.drop_column("review_actions", "idempotency_key")
    op.drop_column("run_revisions", "result_artifact_path")
    op.drop_column("run_revisions", "action_id")
    op.drop_column("run_revisions", "parent_revision")
