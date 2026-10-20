import hashlib
import json
from pathlib import Path

import pytest

from scripts import backup_restore


def test_backup_requires_explicit_lab_write_pause_before_any_command(tmp_path: Path, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(backup_restore, "_compose", lambda *args, **kwargs: calls.append((args, kwargs)))
    with pytest.raises(ValueError, match="lab"):
        backup_restore.create_backup(
            tmp_path / "backup",
            run_id=None,
            base_url="http://127.0.0.1:8000",
            project="reconcileengine",
            pause_lab_writes=True,
        )
    assert calls == []


def test_artifact_inventory_detects_changed_missing_and_extra_files(tmp_path: Path) -> None:
    original = tmp_path / "result.json"
    original.write_text('{"cash": 123}', encoding="utf-8")
    inventory = backup_restore._artifact_inventory(tmp_path)
    backup_restore._verify_artifacts(tmp_path, inventory)
    original.write_text('{"cash": 124}', encoding="utf-8")
    with pytest.raises(AssertionError, match="artifact"):
        backup_restore._verify_artifacts(tmp_path, inventory)
    original.write_text('{"cash": 123}', encoding="utf-8")
    (tmp_path / "untracked.json").write_text("{}", encoding="utf-8")
    with pytest.raises(AssertionError, match="artifact"):
        backup_restore._verify_artifacts(tmp_path, inventory)
    original.unlink()
    with pytest.raises(AssertionError, match="artifact"):
        backup_restore._verify_artifacts(tmp_path, inventory)


def test_compose_command_always_scopes_config_directory_and_project(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(backup_restore, "_command", lambda args, **kwargs: calls.append(args) or "")
    backup_restore._compose(["ps"], project="smartrecon_lab")
    assert calls[0][:2] == ["docker", "compose"]
    assert calls[0][calls[0].index("--project-name") + 1] == "smartrecon_lab"
    assert "--project-directory" in calls[0]
    assert "--file" in calls[0]


def test_restore_rejects_retagged_backup_image_before_creating_resources(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "artifacts").mkdir()
    dump = b"synthetic dump"
    (tmp_path / "postgres.dump").write_bytes(dump)
    manifest = {
        "database": {"filename": "postgres.dump", "sha256": hashlib.sha256(dump).hexdigest()},
        "artifacts": {"directory": "artifacts", "files": {}},
        "images": {"backend": {"reference": "smartrecon-backend:backup-test", "id": "sha256:expected"}},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    calls = []
    monkeypatch.setattr(backup_restore, "_command", lambda *args, **kwargs: '[{"Id":"sha256:wrong"}]')
    monkeypatch.setattr(backup_restore, "_compose", lambda *args, **kwargs: calls.append((args, kwargs)))
    with pytest.raises(AssertionError, match="image"):
        backup_restore.restore_drill(tmp_path)
    assert calls == []


def test_matching_mutation_qa_refuses_non_lab_urls() -> None:
    from scripts.qa_matching import exercise

    for address in ("http://localhost:8000", "http://127.0.0.1:5173", "https://example.org:8002"):
        with pytest.raises(ValueError, match="restricted"):
            exercise(address)
