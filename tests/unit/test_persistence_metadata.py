from backend.smartrecon_api.db import models  # noqa: F401
from backend.smartrecon_api.db.database import Base


def test_required_operational_tables_are_registered() -> None:
    assert {
        "upload_sessions",
        "runs",
        "run_revisions",
        "review_actions",
        "match_groups",
        "allocation_edges",
        "artifact_manifest",
    } <= set(Base.metadata.tables)
