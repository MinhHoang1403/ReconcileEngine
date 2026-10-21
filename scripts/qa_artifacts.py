"""Read-only checksum audit for persisted artifacts; no export/rewrite/migration requests."""

import argparse
import json
from pathlib import Path

from scripts.lab_environment import command


def audit(project: str, directory: Path) -> dict:
    if project not in {"smartrecon_lab", "reconcileengine"}:
        raise ValueError("Only the two known projects may be audited")
    code = """
import hashlib,json
from pathlib import Path
from sqlalchemy import select,text
from backend.smartrecon_api.db.database import SessionLocal
from backend.smartrecon_api.db.models import ArtifactManifest
from backend.smartrecon_api.services.artifacts import resolve_artifact_path
failures=[]
counts={}
with SessionLocal() as db:
    db.execute(text('SET TRANSACTION READ ONLY'))
    rows=db.scalars(select(ArtifactManifest)).all()
    for row in rows:
        counts[row.artifact_type]=counts.get(row.artifact_type,0)+1
        path=resolve_artifact_path(row.relative_path)
        if not path.is_file():
            failures.append({'id':row.id,'type':row.artifact_type,'run_id':row.run_id,'path':row.relative_path,'missing':True})
        elif path.stat().st_size != row.byte_size or hashlib.sha256(path.read_bytes()).hexdigest() != row.sha256:
            failures.append({'id':row.id,'type':row.artifact_type,'run_id':row.run_id,'path':row.relative_path,'missing':False})
print(json.dumps({'counts':counts,'total':len(rows),'mismatches':failures}))
"""
    return json.loads(
        command(
            [
                "docker",
                "compose",
                "--project-directory",
                str(directory),
                "--project-name",
                project,
                "exec",
                "-T",
                "backend",
                "/app/.venv/bin/python",
                "-c",
                code,
            ],
            directory=directory,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.project, args.directory.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"total": result["total"], "mismatches": len(result["mismatches"]), "counts": result["counts"]}))


if __name__ == "__main__":
    main()
