"""Read isolated evaluation labels without exposing them to matching runtime."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TruthEdge:
    case_id: str
    truth_group_id: str
    order_id: str
    bank_txn_id: str
    allocated_cash_minor: int
    relation: str


@dataclass(frozen=True, slots=True)
class GroundTruth:
    edges: tuple[TruthEdge, ...]
    case_scenarios: dict[str, str]
    manifest: dict[str, object]

    def subset(self, split: str) -> GroundTruth:
        """Create a stable development/holdout split from case IDs.

        The split is independent of predictions and labels. Development contains
        cases whose SHA-256 first byte is even; holdout contains the odd half.
        """
        if split not in {"development", "holdout"}:
            raise ValueError("split phải là development hoặc holdout")
        selected = {
            case_id
            for case_id in self.case_scenarios
            if (hashlib.sha256(case_id.encode()).digest()[0] % 2 == 0) == (split == "development")
        }
        return GroundTruth(
            edges=tuple(edge for edge in self.edges if edge.case_id in selected),
            case_scenarios={case_id: value for case_id, value in self.case_scenarios.items() if case_id in selected},
            manifest={**self.manifest, "evaluation_split": split, "split_rule": "sha256(case_id)[0] parity"},
        )


def load_ground_truth(directory: Path) -> GroundTruth:
    """Load truth edges/cases and manifest from an evaluation-only directory."""
    with (directory / "truth_edges.csv").open(encoding="utf-8", newline="") as handle:
        edges = tuple(
            TruthEdge(
                case_id=row["case_id"],
                truth_group_id=row["truth_group_id"],
                order_id=row["order_id"],
                bank_txn_id=row["bank_txn_id"],
                allocated_cash_minor=int(row["allocated_cash_minor"]),
                relation=row["truth_relation"],
            )
            for row in csv.DictReader(handle)
        )
    with (directory / "truth_cases.csv").open(encoding="utf-8", newline="") as handle:
        scenarios = {row["case_id"]: row["scenario"] for row in csv.DictReader(handle)}
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    return GroundTruth(edges=edges, case_scenarios=scenarios, manifest=manifest)
