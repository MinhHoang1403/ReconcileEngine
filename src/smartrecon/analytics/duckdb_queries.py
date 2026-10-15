"""Embedded DuckDB queries for analytical cross-checks, never transactional state."""

from typing import Any

import duckdb
import pandas as pd

from smartrecon.domain.models import AllocationEdge


def allocation_totals(edges: list[AllocationEdge]) -> dict[str, Any]:
    """Cross-check effective edge totals and distinct denominators in DuckDB."""
    frame = pd.DataFrame(
        [
            {
                "order_id": edge.order_id,
                "bank_txn_id": edge.bank_txn_id,
                "allocated_cash_minor": edge.allocated_cash_minor,
            }
            for edge in edges
        ],
        columns=["order_id", "bank_txn_id", "allocated_cash_minor"],
    )
    if frame.empty:
        return {"allocated_cash_minor": 0, "orders_count": 0, "bank_rows_count": 0}
    with duckdb.connect(":memory:") as connection:
        connection.register("effective_edges", frame)
        row = connection.execute(
            """
            SELECT
                COALESCE(SUM(allocated_cash_minor), 0)::BIGINT,
                COUNT(DISTINCT order_id)::BIGINT,
                COUNT(DISTINCT bank_txn_id)::BIGINT
            FROM effective_edges
            """
        ).fetchone()
    assert row is not None
    return {
        "allocated_cash_minor": int(row[0]),
        "orders_count": int(row[1]),
        "bank_rows_count": int(row[2]),
    }
