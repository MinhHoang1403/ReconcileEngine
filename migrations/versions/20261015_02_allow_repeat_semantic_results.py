"""Allow separate runs to share the same deterministic semantic checksum."""

from collections.abc import Sequence

from alembic import op

revision: str = "20261015_02"
down_revision: str | None = "20261015_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace uniqueness with a lookup index for reproducible reruns."""
    op.drop_constraint("runs_semantic_checksum_key", "runs", type_="unique")
    op.create_index("ix_runs_semantic_checksum", "runs", ["semantic_checksum"], unique=False)


def downgrade() -> None:
    """Restore the original uniqueness rule when data permits it."""
    op.drop_index("ix_runs_semantic_checksum", table_name="runs")
    op.create_unique_constraint("runs_semantic_checksum_key", "runs", ["semantic_checksum"])
