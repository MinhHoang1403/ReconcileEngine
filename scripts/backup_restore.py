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
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
RUN_ID_PATTERN = re.compile(r"^[0-9a-f-]{36}$")
RESTORE_PROJECT_PATTERN = re.compile(r"^smartrecon_restore_[0-9a-f]{10}$")
LAB_PROJECT_PATTERN = re.compile(r"^smartrecon_(lab|restore_[0-9a-f]{10})$")


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
    if not project or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project):
        raise ValueError("An explicit valid Compose project is required")
    command = ["docker", "compose", "--project-directory", str(ROOT), "--file", str(ROOT / "compose.yaml")]
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
            'exec psql -X -qAt --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --command="$1"',
            "sh",
            sql,
        ],
        project=project,
        environment=environment,
    )


def database_inventory(project: str, environment: dict[str, str] | None = None) -> list[str]:
    """Read a repeatable table fingerprint; used to reject stale cutover backups."""
    tables = (
        "upload_sessions",
        "runs",
        "run_revisions",
        "review_actions",
        "match_groups",
        "allocation_edges",
        "verified_adjustments",
        "artifact_manifest",
        "import_profiles",
        "alembic_version",
    )
    statements = [
        f"SELECT '{table}', count(*), md5(COALESCE(string_agg(row_text, '' ORDER BY row_text), '')) "
        f"FROM (SELECT row_to_json(t)::text row_text FROM {table} t) rows"
        for table in tables
    ]
    sql = "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; " + " UNION ALL ".join(statements) + "; COMMIT;"
    return sorted(_database_scalar(sql, project=project, environment=environment).splitlines())


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


def _artifact_inventory(directory: Path) -> dict[str, dict[str, Any]]:
    """Checksum every copied file, not just the database dump or an aggregate byte count."""
    return {
        path.relative_to(directory).as_posix(): {"sha256": _sha256(path), "byte_size": path.stat().st_size}
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def _verify_artifacts(directory: Path, expected: dict[str, dict[str, Any]]) -> None:
    if _artifact_inventory(directory) != expected:
        raise AssertionError("Backup artifact inventory differs from the manifest")


def _pin_image(container: dict[str, Any], service: str) -> dict[str, str]:
    """Retain an image under a backup-specific tag before mutable lab tags are rebuilt."""
    image_id = container["Image"]
    inspected = json.loads(_command(["docker", "image", "inspect", image_id]))[0]
    if inspected["Id"] != image_id:
        raise AssertionError("Source image identity differs from the running container")
    reference = f"smartrecon-{service}:backup-{secrets.token_hex(8)}"
    _command(["docker", "image", "tag", image_id, reference])
    return {"reference": reference, "id": image_id}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _validated_run_id(run_id: str | None, *, project: str) -> str:
    selected = run_id or _database_scalar(
        "SELECT id FROM runs ORDER BY completed_at DESC NULLS LAST, created_at DESC LIMIT 1;", project=project
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
        "history_sha256": hashlib.sha256(json.dumps(history["items"], sort_keys=True).encode()).hexdigest(),
    }


def create_backup(
    output_directory: Path,
    *,
    run_id: str | None,
    base_url: str,
    project: str,
    pause_lab_writes: bool = False,
    approved_main_maintenance: bool = False,
    leave_writer_stopped: bool = False,
) -> Path:
    """Drain one verified writer; main requires a separate explicit maintenance approval."""
    main_approved = project == "reconcileengine" and approved_main_maintenance
    lab_approved = bool(LAB_PROJECT_PATTERN.fullmatch(project)) and pause_lab_writes
    if not (main_approved or lab_approved):
        raise ValueError("Consistent backup requires explicit lab write pause or approved main maintenance")
    if leave_writer_stopped and not main_approved:
        raise ValueError("Leaving a writer stopped requires approved main maintenance")
    backend_id = _compose(["ps", "--quiet", "backend"], project=project)
    backend = json.loads(_command(["docker", "inspect", backend_id]))[0]
    if backend["Config"]["Labels"]["com.docker.compose.project"] != project:
        raise ValueError("Backend does not belong to the requested lab project")
    endpoint = urlsplit(base_url)
    published = backend["HostConfig"]["PortBindings"].get("8000/tcp", [])
    if endpoint.hostname not in {"127.0.0.1", "localhost"} or not any(
        item["HostIp"] == "127.0.0.1" and int(item["HostPort"]) == endpoint.port for item in published
    ):
        raise ValueError("Verification URL must address the selected lab backend's loopback port")
    artifact_root = next(
        value.split("=", 1)[1] for value in backend["Config"]["Env"] if value.startswith("ARTIFACTS_PATH=")
    )
    artifact_mount = next(
        mount
        for mount in backend["Mounts"]
        if artifact_root == mount["Destination"] or artifact_root.startswith(mount["Destination"] + "/")
    )
    if artifact_mount["Type"] != "volume" or not artifact_mount["Name"].startswith(project + "_"):
        raise ValueError("Backup lab must own its artifact volume")
    volume_users = _command(["docker", "ps", "--filter", "volume=" + artifact_mount["Name"], "--quiet"]).splitlines()
    if len(volume_users) != 1 or not backend_id.startswith(volume_users[0]):
        raise ValueError("Artifact volume must have exactly one running application writer")
    frontend_id = _compose(["ps", "--all", "--quiet", "frontend"], project=project)
    frontend = json.loads(_command(["docker", "inspect", frontend_id]))[0]
    images = {"backend": _pin_image(backend, "backend"), "frontend": _pin_image(frontend, "frontend")}
    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=False)
    artifact_directory = output_directory / "artifacts"
    artifact_directory.mkdir()
    dump_path = output_directory / "postgres.dump"

    selected_run_id = _validated_run_id(run_id, project=project)
    source = _snapshot(base_url.rstrip("/"), selected_run_id)
    revision = int(source["effective_revision"])
    allocation_row = _database_scalar(
        "SELECT count(*) || '|' || COALESCE(sum(allocated_cash_minor), 0) "
        f"FROM allocation_edges WHERE run_id = '{selected_run_id}' AND revision = {revision};",
        project=project,
    )
    allocation_count, allocation_total = (int(value) for value in allocation_row.split("|"))

    # SIGTERM drains the sole writer before copying either store. Main is never
    # paused implicitly: the caller must have explicit owner maintenance approval.
    _compose(["stop", "--timeout", "60", "backend"], project=project)
    container_dump = f"/tmp/smartrecon-backup-{secrets.token_hex(8)}.dump"
    try:
        stopped = json.loads(_command(["docker", "inspect", backend_id]))[0]
        if stopped["State"]["Running"]:
            raise AssertionError("Lab application writer did not stop")
        active_connections = _database_scalar(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
            "AND pid <> pg_backend_pid() AND backend_type = 'client backend';",
            project=project,
        )
        if int(active_connections) != 0:
            raise AssertionError("Other database clients remain; cannot establish a lab write-free interval")
        current_revision = _database_scalar(
            f"SELECT current_revision FROM runs WHERE id = '{selected_run_id}';", project=project
        )
        if int(current_revision) != revision:
            raise AssertionError("Source revision changed while draining writes; retry backup")
        frozen_database = database_inventory(project)
        _compose(
            [
                "exec",
                "-T",
                "db",
                "sh",
                "-c",
                'pg_dump --format=custom --no-owner --no-acl --username="$POSTGRES_USER" '
                f'--dbname="$POSTGRES_DB" --file={container_dump}',
            ],
            project=project,
        )
        _compose(["cp", f"db:{container_dump}", str(dump_path)], project=project)
        _compose(["cp", f"backend:{artifact_root}/.", str(artifact_directory)], project=project)
    finally:
        _compose(["exec", "-T", "db", "rm", "-f", container_dump], project=project)
        if not leave_writer_stopped:
            _compose(["start", "backend"], project=project)
            _wait_for_url(base_url.rstrip("/") + "/healthz")

    artifact_count, artifact_bytes = _artifact_stats(artifact_directory)
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "format": "smartrecon-backup",
        "source_project": project,
        "approved_main_maintenance": main_approved,
        "consistency": "single_application_writer_drained_and_stopped",
        "database_inventory": frozen_database,
        "images": images,
        "database": {
            "filename": dump_path.name,
            "sha256": _sha256(dump_path),
            "byte_size": dump_path.stat().st_size,
        },
        "artifacts": {
            "directory": artifact_directory.name,
            "file_count": artifact_count,
            "byte_size": artifact_bytes,
            "files": _artifact_inventory(artifact_directory),
        },
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
            "ARTIFACTS_PATH": "/artifacts",
        }
    )
    return environment, backend_port, frontend_port


def restore_drill(
    backup_directory: Path,
    *,
    keep: bool = False,
    exercise: Callable[[str, dict[str, str], str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Restore a backup into isolated volumes and verify the persisted business state."""
    backup_directory = backup_directory.resolve()
    manifest = json.loads((backup_directory / "manifest.json").read_text(encoding="utf-8"))
    dump_path = backup_directory / manifest["database"]["filename"]
    artifact_directory = backup_directory / manifest["artifacts"]["directory"]
    if _sha256(dump_path) != manifest["database"]["sha256"]:
        raise AssertionError("PostgreSQL dump checksum does not match the manifest")
    _verify_artifacts(artifact_directory, manifest["artifacts"]["files"])

    project = f"smartrecon_restore_{secrets.token_hex(5)}"
    if not RESTORE_PROJECT_PATTERN.fullmatch(project):
        raise AssertionError("Unsafe restore project name")
    environment, backend_port, frontend_port = _restore_environment()
    for service in ("backend", "frontend"):
        image = manifest["images"][service]
        inspected = json.loads(_command(["docker", "image", "inspect", image["reference"]]))[0]
        if inspected["Id"] != image["id"]:
            raise AssertionError("Backup image tag no longer refers to the recorded image")
        environment[f"{service.upper()}_IMAGE"] = image["reference"]
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

        _compose(["up", "--no-build", "--pull", "never", "-d", "backend"], project=project, environment=environment)
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
        inventory_code = (
            "import hashlib,json; from pathlib import Path; root=Path('/artifacts'); "
            "print(json.dumps({p.relative_to(root).as_posix(): "
            "{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'byte_size':p.stat().st_size} "
            "for p in root.rglob('*') if p.is_file()}))"
        )
        restored_files = json.loads(
            _compose(
                ["exec", "-T", "backend", "/app/.venv/bin/python", "-c", inventory_code],
                project=project,
                environment=environment,
            )
        )
        if restored_files != manifest["artifacts"]["files"]:
            raise AssertionError("Restored artifact bytes differ from the backup manifest")
        _compose(["restart", "backend"], project=project, environment=environment)
        _wait_for_url(f"{api_url}/healthz")
        _compose(["up", "--no-build", "--pull", "never", "-d", "frontend"], project=project, environment=environment)
        _wait_for_url(f"http://127.0.0.1:{frontend_port}")

        restored = _snapshot(api_url, run_id)
        if restored != {
            key: verification[key]
            for key in ("run_id", "effective_revision", "semantic_checksum", "kpis", "history_total", "history_sha256")
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
        if exercise is not None:
            result["exercise"] = exercise(project, environment, api_url, f"http://127.0.0.1:{frontend_port}")
        return result
    finally:
        if not keep:
            if not RESTORE_PROJECT_PATTERN.fullmatch(project):
                raise AssertionError("Refusing to remove volumes for an unvalidated project name")
            # Preserve restored volumes and images for inspection; no automated deletion.
            _compose(["stop"], project=project, environment=environment)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("output_directory", type=Path)
    backup_parser.add_argument("--run-id")
    backup_parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    backup_parser.add_argument("--project", required=True)
    backup_parser.add_argument("--pause-lab-writes", action="store_true")
    backup_parser.add_argument("--approve-main-maintenance", action="store_true")
    backup_parser.add_argument("--leave-writer-stopped", action="store_true")
    drill_parser = subparsers.add_parser("restore-drill")
    drill_parser.add_argument("backup_directory", type=Path)
    drill_parser.add_argument("--keep", action="store_true")
    drill_parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()

    if arguments.action == "backup":
        manifest = create_backup(
            arguments.output_directory,
            run_id=arguments.run_id,
            base_url=arguments.base_url,
            project=arguments.project,
            pause_lab_writes=arguments.pause_lab_writes,
            approved_main_maintenance=arguments.approve_main_maintenance,
            leave_writer_stopped=arguments.leave_writer_stopped,
        )
        print(json.dumps({"manifest": str(manifest)}, ensure_ascii=False))
    else:
        result = restore_drill(arguments.backup_directory, keep=arguments.keep)
        encoded = json.dumps(result, ensure_ascii=False, indent=2)
        if arguments.output:
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(encoded + "\n", encoding="utf-8")
        print(encoded)


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, OSError, RuntimeError, TimeoutError, ValueError) as error:
        print(f"backup/restore failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
