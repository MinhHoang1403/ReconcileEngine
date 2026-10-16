from pathlib import Path

import pytest

from backend.smartrecon_api.config import get_settings
from backend.smartrecon_api.services.artifacts import (
    relative_artifact_path,
    resolve_artifact_path,
    run_directory,
    upload_directory,
)


def test_artifact_identifiers_and_relative_paths_cannot_escape_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "artifacts_path", tmp_path / "artifacts")

    with pytest.raises(ValueError, match="identifier"):
        upload_directory("../outside")
    with pytest.raises(ValueError, match="identifier"):
        run_directory("run/../../outside")
    with pytest.raises(ValueError, match="path"):
        resolve_artifact_path("../../outside.txt")

    valid = upload_directory("safe-session_01") / "orders.csv"
    valid.write_text("order_id\nO1\n", encoding="utf-8")
    assert relative_artifact_path(valid) == "uploads/safe-session_01/orders.csv"
    assert resolve_artifact_path("uploads/safe-session_01/orders.csv") == valid.resolve()
