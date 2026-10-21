from sqlalchemy import UniqueConstraint

from backend.smartrecon_api.db.models import (
    ArtifactManifest,
    ImportProfile,
    ReconciliationRun,
    ReviewAction,
    RunRevision,
    UploadSession,
)


def test_models_describe_persisted_migrations_without_requiring_schema_changes() -> None:
    # The initial migration allows these timestamps to be NULL and supplies now().
    for model in (UploadSession, ReconciliationRun, RunRevision, ReviewAction, ArtifactManifest):
        assert model.__table__.c.created_at.nullable is True
        assert model.__table__.c.created_at.server_default is not None
    profile = ImportProfile.__table__
    assert profile.c.created_at.nullable is False
    assert profile.c.updated_at.nullable is False
    assert any(
        isinstance(constraint, UniqueConstraint) and list(constraint.columns.keys()) == ["schema_fingerprint"]
        for constraint in profile.constraints
    )
    index = next(index for index in profile.indexes if index.name == "ix_import_profiles_schema_fingerprint")
    assert index.unique is False
