"""Remove approved SmartRecon trial containers/networks, preserving all volumes/images."""

import argparse
import json
import re
import subprocess
from pathlib import Path
from urllib.request import urlopen

TRIAL_PROJECT = re.compile(r"^smartrecon_(lab|restore_[0-9a-f]{10})$")


def select_trials(containers: list[dict]) -> list[dict]:
    """Require both an exact Compose trial project and its owned container name."""
    result = []
    for row in containers:
        project = (row.get("Config", {}).get("Labels") or {}).get("com.docker.compose.project", "")
        if TRIAL_PROJECT.fullmatch(project) and row["Name"].lstrip("/").startswith(project + "-"):
            result.append(row)
    return result


def command(arguments: list[str]) -> str:
    completed = subprocess.run(["docker", *arguments], capture_output=True, text=True, encoding="utf-8", check=True)
    return completed.stdout.strip()


def cleanup(*, approved: bool) -> dict:
    if not approved:
        raise ValueError("Trial container cleanup requires explicit approval")
    with urlopen("http://127.0.0.1:8000/healthz", timeout=10) as response:
        assert json.load(response) == {"status": "ok", "database": "ok"}
    ids = command(["ps", "-aq"]).splitlines()
    containers = json.loads(command(["inspect", *ids]))
    targets = select_trials(containers)
    protected = {row["Id"] for row in containers if row not in targets}
    main_mounts = {
        mount["Name"]
        for row in containers
        if (row.get("Config", {}).get("Labels") or {}).get("com.docker.compose.project") == "reconcileengine"
        for mount in row["Mounts"]
        if mount["Type"] == "volume"
    }
    trial_mounts = {m["Name"] for row in targets for m in row["Mounts"] if m["Type"] == "volume"}
    assert main_mounts and not main_mounts & trial_mounts, "Shared volume: refuse cleanup"
    volumes_before = set(command(["volume", "ls", "--format", "{{.Name}}"]).splitlines())
    images_before = set(command(["image", "ls", "-aq", "--no-trunc"]).splitlines())
    removed = []
    for row in targets:
        identifier = row["Id"]
        if row["State"]["Running"]:
            command(["stop", "--time", "60", identifier])
        assert not json.loads(command(["inspect", identifier]))[0]["State"]["Running"]
        command(["rm", identifier])  # No --volumes/-v, prune or image removal.
        removed.append(row["Name"].lstrip("/"))
    network_ids = command(["network", "ls", "-q"]).splitlines()
    removed_networks = []
    for network in json.loads(command(["network", "inspect", *network_ids])):
        project = (network.get("Labels") or {}).get("com.docker.compose.project", "")
        if TRIAL_PROJECT.fullmatch(project) and not network.get("Containers"):
            command(["network", "rm", network["Id"]])
            removed_networks.append(network["Name"])
    assert set(command(["volume", "ls", "--format", "{{.Name}}"]).splitlines()) == volumes_before
    assert set(command(["image", "ls", "-aq", "--no-trunc"]).splitlines()) == images_before
    assert protected <= set(command(["ps", "-aq", "--no-trunc"]).splitlines())
    with urlopen("http://127.0.0.1:8000/healthz", timeout=10) as response:
        assert json.load(response)["status"] == "ok"
    return {
        "removed_containers": removed,
        "removed_empty_trial_networks": removed_networks,
        "all_volumes_preserved": True,
        "all_images_preserved": True,
        "other_containers_preserved": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve-cleanup", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = cleanup(approved=args.approve_cleanup)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
