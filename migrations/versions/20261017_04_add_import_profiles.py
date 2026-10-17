"""Add reusable import profiles bound to exact source schemas."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_04"
down_revision: str | None = "20261015_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("schema_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("schema_snapshot", sa.JSON(), nullable=False),
        sa.Column("mapping_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schema_fingerprint"),
    )
    op.create_index("ix_import_profiles_schema_fingerprint", "import_profiles", ["schema_fingerprint"])


def downgrade() -> None:
    op.drop_table("import_profiles")
