"""Restore an approved frozen main backup to fresh volumes, preserving old storage."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import time
from pathlib import Path

from dotenv import dotenv_values

from scripts import backup_restore as backup


def deploy(directory: Path, backup_directory: Path, images: dict[str, str], *, approved: bool) -> dict:
    """No implicit writes: exact main project, stopped writer, frozen backup and fresh volumes."""
    if not approved:
        raise ValueError("Main cutover requires explicit owner approval")
    directory = directory.resolve()
    if directory != Path(r"C:\Work\ReconcileEngine").resolve():
        raise ValueError("This local cutover is restricted to the verified main workspace")
    manifest = json.loads((backup_directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("source_project") != "reconcileengine" or not manifest.get("approved_main_maintenance"):
        raise ValueError("Only a frozen approved MAIN backup may be deployed; never Lab data")
    dump = backup_directory / manifest["database"]["filename"]
    artifacts = backup_directory / manifest["artifacts"]["directory"]
    if backup._sha256(dump) != manifest["database"]["sha256"]:
        raise AssertionError("Database backup checksum mismatch")
    backup._verify_artifacts(artifacts, manifest["artifacts"]["files"])
    container = json.loads(backup._command(["docker", "inspect", "reconcileengine-backend-1"]))[0]
    if (
        container["State"]["Running"]
        or container["Config"]["Labels"]["com.docker.compose.project"] != "reconcileengine"
    ):
        raise ValueError("Main writer must be explicitly stopped before cutover")
    if backup.database_inventory("reconcileengine") != manifest["database_inventory"]:
        raise AssertionError("Main database changed since backup; refuse stale cutover")
    generation = secrets.token_hex(5)
    volumes = {
        "POSTGRES_VOLUME": f"reconcileengine_pg_data_{generation}",
        "ARTIFACTS_VOLUME": f"reconcileengine_artifacts_data_{generation}",
    }
    present = set(backup._command(["docker", "volume", "ls", "--format", "{{.Name}}"]).splitlines())
    if present & set(volumes.values()):
        raise AssertionError("Release storage must be fresh")
    environment = {
        **os.environ,
        **{k: v for k, v in dotenv_values(directory / ".env").items() if v is not None},
        **volumes,
    }
    for service, reference in images.items():
        backup._command(["docker", "image", "inspect", reference])
        environment[f"{service.upper()}_IMAGE"] = reference
    environment.update({"BACKEND_PORT": "8000", "FRONTEND_PORT": "5173"})

    def compose(arguments: list[str]) -> str:
        completed = subprocess.run(
            [
                "docker",
                "compose",
                "--project-directory",
                str(directory),
                "-p",
                "reconcileengine",
                "-f",
                str(directory / "compose.yaml"),
                "-f",
                str(directory / "compose.storage.yaml"),
                *arguments,
            ],
            env=environment,
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode:
            raise RuntimeError(f"Compose operation failed ({arguments[0]}): {completed.stderr[-2500:]}")
        return completed.stdout.strip()

    old_volumes = sorted(
        {
            m["Name"]
            for name in ("reconcileengine-backend-1", "reconcileengine-db-1")
            for c in json.loads(backup._command(["docker", "inspect", name]))
            for m in c["Mounts"]
            if m["Type"] == "volume"
        }
    )
    compose(["config", "--quiet"])
    compose(["stop", "--timeout", "60"])
    compose(["up", "-d", "db"])
    deadline = time.monotonic() + 90
    while True:
        try:
            compose(["exec", "-T", "db", "sh", "-c", 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'])
            break
        except RuntimeError:
            if time.monotonic() > deadline:
                raise TimeoutError("Fresh database failed readiness") from None
            time.sleep(1)
    compose(["cp", str(dump), "db:/tmp/smartrecon-cutover.dump"])
    # Database is newly created on a fresh volume. Never pg_restore --clean on old storage.
    compose(
        [
            "exec",
            "-T",
            "db",
            "sh",
            "-c",
            'pg_restore --exit-on-error --no-owner --no-acl --username="$POSTGRES_USER" '
            '--dbname="$POSTGRES_DB" /tmp/smartrecon-cutover.dump',
        ]
    )
    compose(["exec", "-T", "db", "rm", "-f", "/tmp/smartrecon-cutover.dump"])
    # Create, but do not start application writers until artifacts are fully copied.
    compose(["create", "--no-build", "backend"])
    compose(["cp", f"{artifacts}{os.sep}.", "backend:/artifacts/"])
    compose(["run", "--rm", "--no-deps", "--user", "0", "backend", "chown", "-R", "app:app", "/artifacts"])
    compose(["up", "-d", "--no-build", "--pull", "never", "backend"])
    backup._wait_for_url("http://127.0.0.1:8000/healthz")
    compose(["exec", "-T", "backend", "uv", "run", "alembic", "check"])
    if backup.database_inventory("reconcileengine", environment) != manifest["database_inventory"]:
        raise AssertionError("Restored database differs from frozen main backup; frontend remains closed")
    code = (
        "import hashlib,json; from pathlib import Path; root=Path('/artifacts'); "
        "print(json.dumps({p.relative_to(root).as_posix(): {'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),"
        "'byte_size':p.stat().st_size} for p in root.rglob('*') if p.is_file()}))"
    )
    if (
        json.loads(compose(["exec", "-T", "backend", "/app/.venv/bin/python", "-c", code]))
        != manifest["artifacts"]["files"]
    ):
        raise AssertionError("Restored artifacts differ; frontend remains closed")
    expected = manifest["verification"]
    actual = backup._snapshot("http://127.0.0.1:8000", expected["run_id"])
    if any(actual[key] != expected[key] for key in actual):
        raise AssertionError("Run/revision/audit/KPI differs; frontend remains closed")
    compose(["up", "-d", "--no-build", "--pull", "never", "frontend"])
    backup._wait_for_url("http://127.0.0.1:5173")
    return {
        "project": "reconcileengine",
        "storage_environment": volumes,
        "old_volumes_preserved": old_volumes,
        "images": images,
        "main_backup": str(backup_directory),
        "database_exactly_restored": True,
        "artifacts_exactly_restored": True,
        "sample_run_verified": expected["run_id"],
        "schema_revision": "20261017_04",
        "frontend_url": "http://127.0.0.1:5173",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--frontend", required=True)
    parser.add_argument("--approve-main-cutover", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = deploy(
        args.directory,
        args.backup.resolve(),
        {"backend": args.backend, "frontend": args.frontend},
        approved=args.approve_main_cutover,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
