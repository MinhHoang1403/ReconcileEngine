"""Local-volume artifact storage with paths constrained below one configured root."""

import hashlib
from pathlib import Path

from backend.smartrecon_api.config import get_settings


def artifact_root() -> Path:
    root = get_settings().artifacts_path.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def upload_directory(session_id: str) -> Path:
    return _safe_child("uploads", session_id)


def run_directory(run_id: str) -> Path:
    return _safe_child("runs", run_id)


def _safe_child(category: str, identifier: str) -> Path:
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    if not identifier or any(character not in allowed for character in identifier):
        raise ValueError("Artifact identifier không hợp lệ")
    root = artifact_root()
    target = (root / category / identifier).resolve()
    if root not in target.parents:
        raise ValueError("Artifact path vượt ngoài storage root")
    target.mkdir(parents=True, exist_ok=True)
    return target


def relative_artifact_path(path: Path) -> str:
    return str(path.resolve().relative_to(artifact_root())).replace("\\", "/")


def resolve_artifact_path(relative_path: str) -> Path:
    root = artifact_root()
    target = (root / relative_path).resolve()
    if root != target and root not in target.parents:
        raise ValueError("Artifact path không hợp lệ")
    return target


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
