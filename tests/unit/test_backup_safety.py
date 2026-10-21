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


def test_main_approval_cannot_authorize_another_project(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(backup_restore, "_compose", lambda *args, **kwargs: pytest.fail("Must refuse before Docker"))
    with pytest.raises(ValueError, match="approved"):
        backup_restore.create_backup(
            tmp_path / "backup",
            run_id=None,
            base_url="http://localhost:8000",
            project="another_project",
            approved_main_maintenance=True,
        )


def test_cutover_requires_approval_and_exact_main_workspace(tmp_path: Path) -> None:
    from scripts.deploy_release import deploy

    with pytest.raises(ValueError, match="approval"):
        deploy(tmp_path, tmp_path, {}, approved=False)
    with pytest.raises(ValueError, match="workspace"):
        deploy(tmp_path, tmp_path, {}, approved=True)


def test_lab_cannot_leave_writer_stopped_with_main_flag(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="approved main"):
        backup_restore.create_backup(
            tmp_path / "backup",
            run_id=None,
            base_url="http://localhost:8002",
            project="smartrecon_lab",
            pause_lab_writes=True,
            leave_writer_stopped=True,
        )


def test_cutover_rejects_lab_backup_before_any_docker_command(tmp_path: Path, monkeypatch) -> None:
    from scripts.deploy_release import deploy

    (tmp_path / "manifest.json").write_text(json.dumps({"source_project": "smartrecon_lab"}), encoding="utf-8")
    monkeypatch.setattr(backup_restore, "_command", lambda *args, **kwargs: pytest.fail("No Docker allowed"))
    with pytest.raises(ValueError, match="MAIN backup"):
        deploy(Path(r"C:\Work\ReconcileEngine"), tmp_path, {}, approved=True)


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


def test_import_browser_qa_refuses_main_before_creating_files(tmp_path: Path) -> None:
    from scripts.qa_import_workflow import exercise

    for address in ("http://localhost:5173", "http://127.0.0.1:8000", "https://example.org:5174"):
        with pytest.raises(ValueError, match="restricted"):
            exercise(address, 390, 844, tmp_path / "not-created", ["csv"])
    assert not (tmp_path / "not-created").exists()


def test_review_qa_refuses_main_before_http_requests() -> None:
    from scripts.qa_concurrency import run

    with pytest.raises(ValueError, match="restricted"):
        run("http://localhost:8000")


def test_demo_browser_qa_refuses_main_before_launch(monkeypatch) -> None:
    from scripts.browser_smoke import main

    monkeypatch.setattr("sys.argv", ["browser_smoke.py", "--url", "http://localhost:5173"])
    with pytest.raises(ValueError, match="restricted"):
        main()


def test_parallel_export_qa_refuses_main_before_http(tmp_path: Path) -> None:
    from scripts.qa_exports import exercise

    with pytest.raises(ValueError, match="restricted"):
        exercise("http://localhost:8000", tmp_path)
