"""Back up SmartRecon state and prove restoration in an isolated Compose project."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUN_ID_PATTERN = re.compile(r"^[0-9a-f-]{36}$")
RESTORE_PROJECT_PATTERN = re.compile(r"^smartrecon_restore_[0-9a-f]{10}$")


def _command(
    arguments: list[str],
    *,
    environment: dict[str, str] | None = None,
    capture: bool = True,
) -> str:
    completed = subprocess.run(
        arguments,
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=capture,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no diagnostic output"
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {detail}")
    return completed.stdout.strip() if capture else ""


def _compose(
    arguments: list[str],
    *,
    project: str | None = None,
    environment: dict[str, str] | None = None,
) -> str:
    command = ["docker", "compose"]
    if project:
        command.extend(["--project-name", project])
    command.extend(arguments)
    return _command(command, environment=environment)


def _database_scalar(sql: str, *, project: str | None = None, environment: dict[str, str] | None = None) -> str:
    return _compose(
        [
            "exec",
            "-T",
            "db",
            "sh",
            "-c",
            f'psql --no-psqlrc --tuples-only --no-align --username="$POSTGRES_USER" '
            f'--dbname="$POSTGRES_DB" --command={json.dumps(sql)}',
        ],
        project=project,
        environment=environment,
    )


def _request(url: str, *, timeout: float = 60) -> tuple[bytes, str]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read(), response.headers.get("Content-Type", "")


def _json(url: str) -> dict[str, Any]:
    body, content_type = _request(url)
    if "application/json" not in content_type:
        raise AssertionError(f"Expected JSON from {url}, got {content_type}")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise AssertionError(f"Expected a JSON object from {url}")
    return payload


def _wait_for_url(url: str, *, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            body, _ = _request(url, timeout=5)
            if body:
                return
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
        time.sleep(1)
    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_stats(directory: Path) -> tuple[int, int]:
    files = [path for path in directory.rglob("*") if path.is_file()]
    return len(files), sum(path.stat().st_size for path in files)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _validated_run_id(run_id: str | None) -> str:
    selected = run_id or _database_scalar(
        "SELECT id FROM runs ORDER BY completed_at DESC NULLS LAST, created_at DESC LIMIT 1;"
    )
    selected = selected.strip()
    if not RUN_ID_PATTERN.fullmatch(selected):
        raise ValueError("A valid persisted run UUID is required for backup verification")
    return selected


def _snapshot(base_url: str, run_id: str) -> dict[str, Any]:
    run = _json(f"{base_url}/api/runs/{run_id}")
    revision = int(run["effective_revision"])
    dashboard = _json(f"{base_url}/api/runs/{run_id}/dashboard?revision={revision}")
    history = _json(f"{base_url}/api/runs/{run_id}/reviews/history?page_size=200")
    if dashboard["conservation"]["is_valid"] is not True:
        raise AssertionError("The source run violates money conservation")
    return {
        "run_id": run_id,
        "effective_revision": revision,
        "semantic_checksum": run["semantic_checksum"],
        "kpis": dashboard["kpis"],
        "history_total": history["total"],
    }


def create_backup(output_directory: Path, *, run_id: str | None, base_url: str) -> Path:
    """Create one PostgreSQL/artifact backup with a verification manifest."""
    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=False)
    artifact_directory = output_directory / "artifacts"
    artifact_directory.mkdir()
    dump_path = output_directory / "postgres.dump"

    selected_run_id = _validated_run_id(run_id)
    source = _snapshot(base_url.rstrip("/"), selected_run_id)
    revision = int(source["effective_revision"])
    allocation_row = _database_scalar(
        "SELECT count(*) || '|' || COALESCE(sum(allocated_cash_minor), 0) "
        f"FROM allocation_edges WHERE run_id = '{selected_run_id}' AND revision = {revision};"
    )
    allocation_count, allocation_total = (int(value) for value in allocation_row.split("|"))

    container_dump = "/tmp/smartrecon-postgres-backup.dump"
    _compose(
        [
            "exec",
            "-T",
            "db",
            "sh",
            "-c",
            'pg_dump --format=custom --no-owner --no-acl --username="$POSTGRES_USER" '
            f'--dbname="$POSTGRES_DB" --file={container_dump}',
        ]
    )
    try:
        _compose(["cp", f"db:{container_dump}", str(dump_path)])
    finally:
        _compose(["exec", "-T", "db", "rm", "-f", container_dump])
    _compose(["cp", "backend:/artifacts/.", str(artifact_directory)])

    artifact_count, artifact_bytes = _artifact_stats(artifact_directory)
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "format": "smartrecon-backup",
        "database": {
            "filename": dump_path.name,
            "sha256": _sha256(dump_path),
            "byte_size": dump_path.stat().st_size,
        },
        "artifacts": {"directory": artifact_directory.name, "file_count": artifact_count, "byte_size": artifact_bytes},
        "verification": {
            **source,
            "allocation_count": allocation_count,
            "allocation_total_minor": allocation_total,
        },
    }
    manifest_path = output_directory / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest_path


def _restore_environment() -> tuple[dict[str, str], int, int]:
    backend_port = _free_port()
    frontend_port = _free_port()
    password = f"restore_{secrets.token_hex(16)}"
    environment = os.environ.copy()
    environment.update(
        {
            "POSTGRES_DB": "smartrecon_restore",
            "POSTGRES_USER": "smartrecon_restore",
            "POSTGRES_PASSWORD": password,
            "DATABASE_URL": (f"postgresql+psycopg://smartrecon_restore:{password}@db:5432/smartrecon_restore"),
            "BACKEND_PORT": str(backend_port),
            "FRONTEND_PORT": str(frontend_port),
            "DEMO_MODE": "false",
            "CORS_ORIGINS": f"http://127.0.0.1:{frontend_port}",
        }
    )
    return environment, backend_port, frontend_port


def restore_drill(backup_directory: Path, *, keep: bool = False) -> dict[str, Any]:
    """Restore a backup into isolated volumes and verify the persisted business state."""
    backup_directory = backup_directory.resolve()
    manifest = json.loads((backup_directory / "manifest.json").read_text(encoding="utf-8"))
    dump_path = backup_directory / manifest["database"]["filename"]
    artifact_directory = backup_directory / manifest["artifacts"]["directory"]
    if _sha256(dump_path) != manifest["database"]["sha256"]:
        raise AssertionError("PostgreSQL dump checksum does not match the manifest")

    project = f"smartrecon_restore_{secrets.token_hex(5)}"
    if not RESTORE_PROJECT_PATTERN.fullmatch(project):
        raise AssertionError("Unsafe restore project name")
    environment, backend_port, frontend_port = _restore_environment()
    api_url = f"http://127.0.0.1:{backend_port}"
    verification = manifest["verification"]
    run_id = str(verification["run_id"])
    revision = int(verification["effective_revision"])

    try:
        _compose(["up", "-d", "db"], project=project, environment=environment)
        deadline = time.monotonic() + 90
        while True:
            try:
                _database_scalar("SELECT 1;", project=project, environment=environment)
                break
            except RuntimeError as error:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Restored PostgreSQL container did not become ready") from error
                time.sleep(1)

        container_dump = "/tmp/smartrecon-postgres-restore.dump"
        _compose(["cp", str(dump_path), f"db:{container_dump}"], project=project, environment=environment)
        try:
            _compose(
                [
                    "exec",
                    "-T",
                    "db",
                    "sh",
                    "-c",
                    'pg_restore --clean --if-exists --no-owner --no-acl --username="$POSTGRES_USER" '
                    f'--dbname="$POSTGRES_DB" {container_dump}',
                ],
                project=project,
                environment=environment,
            )
        finally:
            _compose(
                ["exec", "-T", "db", "rm", "-f", container_dump],
                project=project,
                environment=environment,
            )

        _compose(["up", "-d", "backend"], project=project, environment=environment)
        _wait_for_url(f"{api_url}/healthz")
        _compose(
            ["cp", f"{artifact_directory}{os.sep}.", "backend:/artifacts/"],
            project=project,
            environment=environment,
        )
        _compose(
            ["exec", "-T", "--user", "0", "backend", "chown", "-R", "app:app", "/artifacts"],
            project=project,
            environment=environment,
        )
        _compose(["restart", "backend"], project=project, environment=environment)
        _wait_for_url(f"{api_url}/healthz")
        _compose(["up", "-d", "frontend"], project=project, environment=environment)
        _wait_for_url(f"http://127.0.0.1:{frontend_port}")

        restored = _snapshot(api_url, run_id)
        if restored != {
            key: verification[key]
            for key in ("run_id", "effective_revision", "semantic_checksum", "kpis", "history_total")
        }:
            raise AssertionError("Restored run metadata, KPI, or audit history differs from the source")
        allocation_row = _database_scalar(
            "SELECT count(*) || '|' || COALESCE(sum(allocated_cash_minor), 0) "
            f"FROM allocation_edges WHERE run_id = '{run_id}' AND revision = {revision};",
            project=project,
            environment=environment,
        )
        count, total = (int(value) for value in allocation_row.split("|"))
        if count != verification["allocation_count"] or total != verification["allocation_total_minor"]:
            raise AssertionError("Restored allocation edges differ from the source")
        export, content_type = _request(f"{api_url}/api/runs/{run_id}/exports?format=xlsx&expected_revision={revision}")
        if not export.startswith(b"PK") or "spreadsheet" not in content_type:
            raise AssertionError("Restored run did not produce a valid XLSX export")
        result = {
            "project": project,
            "run_id": run_id,
            "effective_revision": revision,
            "history_total": restored["history_total"],
            "allocation_count": count,
            "allocation_total_minor": total,
            "confirmed_cash_allocated_minor": restored["kpis"]["confirmed_cash_allocated_minor"],
            "export_byte_size": len(export),
            "conservation_valid": True,
            "frontend_url": f"http://127.0.0.1:{frontend_port}",
        }
        return result
    finally:
        if not keep:
            if not RESTORE_PROJECT_PATTERN.fullmatch(project):
                raise AssertionError("Refusing to remove volumes for an unvalidated project name")
            _compose(
                ["down", "--volumes", "--remove-orphans"],
                project=project,
                environment=environment,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("output_directory", type=Path)
    backup_parser.add_argument("--run-id")
    backup_parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    drill_parser = subparsers.add_parser("restore-drill")
    drill_parser.add_argument("backup_directory", type=Path)
    drill_parser.add_argument("--keep", action="store_true")
    arguments = parser.parse_args()

    if arguments.action == "backup":
        manifest = create_backup(arguments.output_directory, run_id=arguments.run_id, base_url=arguments.base_url)
        print(json.dumps({"manifest": str(manifest)}, ensure_ascii=False))
    else:
        print(json.dumps(restore_drill(arguments.backup_directory, keep=arguments.keep), ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, OSError, RuntimeError, TimeoutError, ValueError) as error:
        print(f"backup/restore failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
