from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK = ROOT / "notebooks" / "reconciliation_research.ipynb"


def test_research_notebook_uses_public_engine_and_runs_from_clean_kernel() -> None:
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    source = "\n".join("".join(cell.get("source", "")) for cell in notebook.cells)
    assert "from smartrecon.engine import run_reconciliation" in source
    assert "C:\\Work" not in source

    executed = NotebookClient(
        deepcopy(notebook),
        timeout=180,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT)}},
    ).execute()
    errors = [output for cell in executed.cells for output in cell.get("outputs", []) if output.output_type == "error"]
    assert errors == []
