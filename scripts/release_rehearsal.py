"""Rehearse application rollback before/after new writes on disposable restored copies."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from scripts import backup_restore as backup
from scripts.qa_concurrency import ApiClient, _command, _new_demo_run

TABLES = (
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


def state(project: str, environment: dict[str, str]) -> dict:
    """Hash all rows/files, without recording secrets or financial cell values."""
    if not backup.RESTORE_PROJECT_PATTERN.fullmatch(project):
        raise ValueError("Rehearsal may operate only on a validated restore project")
    sql = (
        "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; "
        + " UNION ALL ".join(
            f"SELECT '{table}', count(*), md5(COALESCE(string_agg(row_text, '' ORDER BY row_text), '')) "
            f"FROM (SELECT row_to_json(t)::text row_text FROM {table} t) rows"
            for table in TABLES
        )
        + "; COMMIT;"
    )
    rows = sorted(backup._database_scalar(sql, project=project, environment=environment).splitlines())
    code = (
        "import hashlib,json; from pathlib import Path; root=Path('/artifacts'); "
        "items=sorted((p.relative_to(root).as_posix(),p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest()) "
        "for p in root.rglob('*') if p.is_file()); "
        "print(json.dumps({'files':len(items),'bytes':sum(x[1] for x in items),"
        "'sha256':hashlib.sha256(json.dumps(items).encode()).hexdigest()}))"
    )
    artifacts = json.loads(
        backup._compose(
            ["exec", "-T", "backend", "/app/.venv/bin/python", "-c", code], project=project, environment=environment
        )
    )
    return {"database": rows, "artifacts": artifacts}


def verified_image(reference: str) -> str:
    inspected = json.loads(backup._command(["docker", "image", "inspect", reference]))[0]
    return inspected["Id"]


def rehearse(backup_directory: Path, candidate: dict[str, str], old: dict[str, str], output: Path) -> dict:
    for reference in [*candidate.values(), *old.values()]:
        verified_image(reference)

    def exercise(project: str, environment: dict[str, str], api_url: str, frontend_url: str) -> dict:
        environment = {**environment, "DEMO_MODE": "true"}

        def switch(images: dict[str, str]) -> None:
            environment.update({f"{service.upper()}_IMAGE": ref for service, ref in images.items()})
            backup._compose(
                ["up", "-d", "--no-build", "--pull", "never", "backend", "frontend"],
                project=project,
                environment=environment,
            )
            backup._wait_for_url(api_url + "/healthz")
            backup._wait_for_url(frontend_url)

        original = state(project, environment)
        switch(candidate)
        backup._compose(
            ["exec", "-T", "backend", "uv", "run", "alembic", "check"], project=project, environment=environment
        )
        assert state(project, environment) == original
        # Simulate application outage after upgrade, before any new write.
        backup._compose(["stop", "backend"], project=project, environment=environment)
        switch(old)
        assert state(project, environment) == original
        switch(candidate)
        assert state(project, environment) == original
        client = ApiClient(api_url)
        run_id = _new_demo_run(client)
        queue = client.json("GET", f"/api/runs/{run_id}/reviews?page_size=200")
        target = next(item for item in queue["items"] if item["can_approve"])
        approved = client.json(
            "POST",
            f"/api/runs/{run_id}/reviews/approve",
            _command(target["group_id"], "rehearsal-approval", "Synthetic rollback rehearsal", 0),
        )
        snapshot = backup._snapshot(api_url, run_id)
        assert snapshot["effective_revision"] == 1
        after_write = state(project, environment)
        # Capture a NEW consistent backup after new business state exists. Never
        # switch to the old database snapshot and pretend these writes survived.
        fresh_backup = output.parent / (output.stem + "-after-writes")
        saved_environment = os.environ.copy()
        try:
            os.environ.update(environment)
            backup.create_backup(fresh_backup, run_id=run_id, base_url=api_url, project=project, pause_lab_writes=True)
        finally:
            os.environ.clear()
            os.environ.update(saved_environment)
        assert state(project, environment) == after_write
        backup._compose(["stop", "backend"], project=project, environment=environment)
        switch(old)
        assert state(project, environment) == after_write
        assert backup._snapshot(api_url, run_id) == snapshot
        switch(candidate)
        assert state(project, environment) == after_write
        assert backup._snapshot(api_url, run_id) == snapshot
        status, content, _ = client.request("GET", f"/api/runs/{run_id}/exports?format=xlsx&expected_revision=1")
        assert status == 200 and content.startswith(b"PK")
        return {
            "rollback_before_writes": True,
            "rollback_after_writes": True,
            "all_existing_rows_files_preserved": True,
            "new_run_id": run_id,
            "new_revision": 1,
            "new_history_total": snapshot["history_total"],
            "approved_response": approved,
            "fresh_backup": str(fresh_backup),
            "export_bytes": len(content),
            "state_sha256_after_new_writes": hashlib.sha256(
                json.dumps(after_write, sort_keys=True).encode()
            ).hexdigest(),
            "candidate_images": {key: {"reference": ref, "id": verified_image(ref)} for key, ref in candidate.items()},
            "rollback_images": {key: {"reference": ref, "id": verified_image(ref)} for key, ref in old.items()},
            "schema_revision": "20261017_04",
            "schema_migrations_added": 0,
        }

    result = backup.restore_drill(backup_directory, exercise=exercise)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--frontend", required=True)
    parser.add_argument("--old-backend", required=True)
    parser.add_argument("--old-frontend", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = rehearse(
        args.backup.resolve(),
        {"backend": args.backend, "frontend": args.frontend},
        {
            "backend": args.old_backend,
            "frontend": args.old_frontend,
        },
        args.output.resolve(),
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
