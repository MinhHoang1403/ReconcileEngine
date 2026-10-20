"""Provision lab-only credentials and collect a read-only Docker/SQL baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import secrets
import shutil
import socket
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def command(arguments: list[str], *, directory: Path = ROOT) -> str:
    result = subprocess.run(arguments, cwd=directory, capture_output=True, text=True, encoding="utf-8", check=False)
    if result.returncode:
        raise RuntimeError(f"{arguments[0]} failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout.strip()


def initialize() -> None:
    """Create a secret file once; never overwrite existing credentials or use main image tags."""
    branch = command(["git", "branch", "--show-current"])
    if branch == "main":
        raise ValueError("Lab initialization must run from a separate research worktree")
    commit = command(["git", "rev-parse", "HEAD"])
    for port in (8002, 5174):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    password = secrets.token_hex(24)
    lines = [
        "COMPOSE_PROJECT_NAME=smartrecon_lab",
        "COMPOSE_FILE=compose.yaml;compose.lab.yaml"
        if platform.system() == "Windows"
        else "COMPOSE_FILE=compose.yaml:compose.lab.yaml",
        "POSTGRES_DB=smartrecon_lab",
        "POSTGRES_USER=smartrecon_lab",
        f"POSTGRES_PASSWORD={password}",
        f"DATABASE_URL=postgresql+psycopg://smartrecon_lab:{password}@db:5432/smartrecon_lab",
        "ARTIFACTS_PATH=/artifacts/lab",
        "BACKEND_PORT=8002",
        "FRONTEND_PORT=5174",
        "CORS_ORIGINS=http://127.0.0.1:5174,http://localhost:5174",
        "DEMO_MODE=true",
        f"BACKEND_IMAGE=smartrecon-backend:lab-{commit[:12]}",
        f"FRONTEND_IMAGE=smartrecon-frontend:lab-{commit[:12]}",
    ]
    with (ROOT / ".env").open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    print("Created ignored lab credentials; secrets were not printed.")


def inventory(project: str, directory: Path, api_url: str) -> dict[str, Any]:
    """Read container identity, SQL state and persisted run KPIs without writing to the app."""
    prefix = ["docker", "compose", "--project-directory", str(directory), "--project-name", project]
    identifiers = command([*prefix, "ps", "--all", "--quiet"], directory=directory).splitlines()
    containers = json.loads(command(["docker", "inspect", *identifiers])) if identifiers else []
    sanitized = [
        {
            "id": row["Id"],
            "name": row["Name"],
            "service": row["Config"]["Labels"]["com.docker.compose.service"],
            "image_id": row["Image"],
            "image_tag": row["Config"]["Image"],
            "state": row["State"]["Status"],
            "health": row["State"].get("Health", {}).get("Status"),
            "exit_code": row["State"]["ExitCode"],
            "mounts": row["Mounts"],
            "networks": sorted(row["NetworkSettings"]["Networks"]),
            "ports": row["HostConfig"]["PortBindings"],
        }
        for row in containers
    ]
    # Serialize each table in primary-key-independent row order. Only hashes/counts leave PostgreSQL.
    tables = [
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
    ]
    statements = [
        f"SELECT '{table}', count(*), md5(COALESCE(string_agg(row_text, '' ORDER BY row_text), '')) "
        f"FROM (SELECT row_to_json(t)::text row_text FROM {table} t) rows"
        for table in tables
    ]
    sql = "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; " + " UNION ALL ".join(statements) + "; COMMIT;"
    state_text = command(
        [
            *prefix,
            "exec",
            "-T",
            "db",
            "sh",
            "-c",
            'exec psql -X -qAt --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --command="$1"',
            "sh",
            sql,
        ],
        directory=directory,
    )
    # SQL is passed as a process argument, not interpolated into a host shell.
    database = sorted(line.split("|") for line in state_text.splitlines() if "|" in line)
    with urlopen(api_url.rstrip("/") + "/healthz", timeout=10) as response:
        health = json.load(response)
    runs: list[dict[str, Any]] = []
    selected_sql = "SELECT id FROM runs ORDER BY created_at DESC LIMIT 3"
    run_ids = command(
        [
            *prefix,
            "exec",
            "-T",
            "db",
            "sh",
            "-c",
            'exec psql -X -qAt --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --command="$1"',
            "sh",
            selected_sql,
        ],
        directory=directory,
    ).splitlines()
    for run_id in run_ids:
        with urlopen(f"{api_url}/api/runs/{run_id}", timeout=10) as response:
            run = json.load(response)
        revision = run["effective_revision"]
        with urlopen(f"{api_url}/api/runs/{run_id}/dashboard?revision={revision}", timeout=20) as response:
            dashboard = json.load(response)
        runs.append({"run": run, "kpis": dashboard["kpis"], "conservation": dashboard["conservation"]})
    artifact_code = (
        "import hashlib,json,os; from pathlib import Path; root=Path(os.environ['ARTIFACTS_PATH']); "
        "files=sorted(p for p in root.rglob('*') if p.is_file()); "
        "items=[(p.relative_to(root).as_posix(),p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest()) "
        "for p in files]; print(json.dumps({'file_count':len(items),'byte_size':sum(x[1] for x in items),"
        "'sha256':hashlib.sha256(json.dumps(items).encode()).hexdigest()}))"
    )
    artifacts = json.loads(
        command([*prefix, "exec", "-T", "backend", "/app/.venv/bin/python", "-c", artifact_code], directory=directory)
    )
    return {
        "captured_at": datetime.now(UTC).isoformat(),
        "project": project,
        "git_commit": command(["git", "rev-parse", "HEAD"], directory=directory),
        "git_branch": command(["git", "branch", "--show-current"], directory=directory),
        "git_status": command(["git", "status", "--short"], directory=directory),
        "docker_version": command(["docker", "version", "--format", "{{.Server.Version}}"]),
        "compose_version": command(["docker", "compose", "version", "--short"]),
        "host_python": platform.python_version(),
        "host_platform": platform.platform(),
        "disk_free_bytes": shutil.disk_usage(directory).free,
        "containers": sanitized,
        "database": database,
        "database_fingerprint": hashlib.sha256(json.dumps(database).encode()).hexdigest(),
        "health": health,
        "artifacts": artifacts,
        "sample_runs": runs,
    }


def compare_inventories(before: dict[str, Any], after: dict[str, Any], lab: dict[str, Any]) -> dict[str, bool]:
    """Fail if any main business state or identity changed, or if storage/network is shared."""
    checks = {
        "main_database_unchanged": sorted(before["database"]) == sorted(after["database"]),
        "main_artifacts_unchanged": before["artifacts"] == after["artifacts"],
        "main_sample_runs_unchanged": before["sample_runs"] == after["sample_runs"],
        "main_containers_unchanged": before["containers"] == after["containers"],
        "main_health_ok": after["health"] == {"status": "ok", "database": "ok"},
        "lab_health_ok": lab["health"] == {"status": "ok", "database": "ok"},
    }
    main_volumes = {
        mount["Name"] for row in after["containers"] for mount in row["mounts"] if mount["Type"] == "volume"
    }
    lab_volumes = {mount["Name"] for row in lab["containers"] for mount in row["mounts"] if mount["Type"] == "volume"}
    main_networks = {network for row in after["containers"] for network in row["networks"]}
    lab_networks = {network for row in lab["containers"] for network in row["networks"]}
    checks["volumes_disjoint"] = bool(main_volumes and lab_volumes) and not main_volumes & lab_volumes
    checks["networks_disjoint"] = bool(main_networks and lab_networks) and not main_networks & lab_networks
    if not all(checks.values()):
        raise AssertionError(f"Isolation checks failed: {[key for key, valid in checks.items() if not valid]}")
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["initialize", "inventory"])
    parser.add_argument("--project")
    parser.add_argument("--directory", type=Path, default=ROOT)
    parser.add_argument("--api-url")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.action == "initialize":
        initialize()
        return
    if not args.project or not args.api_url or not args.output:
        parser.error("inventory requires --project, --api-url and --output")
    payload = inventory(args.project, args.directory.resolve(), args.api_url.rstrip("/"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "database_fingerprint": payload["database_fingerprint"]}))


if __name__ == "__main__":
    main()
