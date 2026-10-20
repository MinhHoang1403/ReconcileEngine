"""Compare bounded subset proposals with isolated integer CP-SAT, never allocate cash."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import statistics
import subprocess
import time
import tracemalloc
from dataclasses import asdict, dataclass
from datetime import date
from itertools import combinations
from pathlib import Path

from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.models import BankTransaction, Order
from smartrecon.domain.statuses import AmountBasis, Currency, Direction
from smartrecon.matching.grouping import bounded_group_candidates


@dataclass(frozen=True)
class SubsetCase:
    name: str
    amounts: tuple[int, ...]
    target: int
    relation: str = "N:1"
    max_size: int = 3
    combination_budget: int = 2000
    solution_limit: int = 10000
    time_limit_seconds: float = 1.0


def cases() -> tuple[SubsetCase, ...]:
    return (
        SubsetCase("unique_group", (100000, 200000), 300000),
        SubsetCase("unique_split", (100000, 200000), 300000, relation="1:N"),
        SubsetCase("equal_totals", (100000, 100000, 200000, 200000), 300000),
        SubsetCase("large_block", tuple(index * 10000 for index in range(1, 22)), 410000),
        SubsetCase("four_participants", (100000, 200000, 400000, 800000), 1500000, max_size=4),
        SubsetCase("truncated_enumeration", tuple(range(10000, 210000, 10000)), 390000, combination_budget=1),
        SubsetCase("competing_explosion", (10000,) * 80, 40000, max_size=4, solution_limit=5),
        SubsetCase("time_limit_before_search", (100000, 200000), 300000, time_limit_seconds=0.0),
    )


def oracle_subsets(case: SubsetCase) -> set[tuple[int, ...]]:
    """Exhaustive small-domain mathematical oracle, without importing any tested solver."""
    if len(case.amounts) > 24:
        raise ValueError("Enumerating this oracle would exceed its declared small-domain scope")
    return {
        subset
        for size in range(2, case.max_size + 1)
        for subset in combinations(range(len(case.amounts)), size)
        if sum(case.amounts[index] for index in subset) == case.target
    }


def bounded(case: SubsetCase) -> dict:
    day = date(2026, 10, 20)

    def bank(identifier: str, amount: int) -> BankTransaction:
        return BankTransaction(identifier, day, amount, Direction.CREDIT, AmountBasis.POSTED_CASH, Currency.VND)

    if case.relation == "N:1":
        orders = [Order(str(index), day, amount, Currency.VND) for index, amount in enumerate(case.amounts)]
        banks = [bank("target", case.target)]
    else:
        orders = [Order("target", day, case.target, Currency.VND)]
        banks = [bank(str(index), amount) for index, amount in enumerate(case.amounts)]
    proposals, exhausted = bounded_group_candidates(
        orders,
        banks,
        ReconciliationPolicy(
            Currency.VND,
            max_group_orders=case.max_size,
            max_split_bank_rows=case.max_size,
            max_combinations_per_case=case.combination_budget,
        ),
    )
    assert not any(proposal.auto_confirm for proposal in proposals)
    solutions = {
        tuple(sorted(map(int, proposal.order_ids if case.relation == "N:1" else proposal.bank_txn_ids)))
        for proposal in proposals
    }
    return {
        "solutions": sorted(solutions),
        "complete": not exhausted,
        "status": "EXHAUSTED" if exhausted else "COMPLETE",
    }


def cp_subsets(case: SubsetCase) -> dict:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    selected = [model.new_bool_var(f"participant_{index}") for index in range(len(case.amounts))]
    model.add(sum(amount * variable for amount, variable in zip(case.amounts, selected, strict=True)) == case.target)
    model.add(sum(selected) >= 2)
    model.add(sum(selected) <= case.max_size)

    class Collector(cp_model.CpSolverSolutionCallback):
        def __init__(self) -> None:
            super().__init__()
            self.solutions: set[tuple[int, ...]] = set()
            self.stopped = False

        def on_solution_callback(self) -> None:
            self.solutions.add(tuple(index for index, variable in enumerate(selected) if self.value(variable)))
            if len(self.solutions) >= case.solution_limit:
                self.stopped = True
                self.stop_search()

    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    solver.parameters.max_time_in_seconds = case.time_limit_seconds
    collector = Collector()
    status = solver.solve(model, collector)
    return {
        "solutions": sorted(collector.solutions),
        "status": solver.status_name(status),
        "complete": not collector.stopped and status in {cp_model.OPTIMAL, cp_model.INFEASIBLE},
        "stopped_at_solution_limit": collector.stopped,
    }


def flow_example() -> dict:
    """Show that equal M:N totals admit multiple legal integer flows, not a verified link."""
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    demand, supply = (100000, 200000), (150000, 150000)
    flows = [
        [model.new_int_var(0, min(need, cash), f"cash_{i}_{j}") for j, cash in enumerate(supply)]
        for i, need in enumerate(demand)
    ]
    for i, need in enumerate(demand):
        model.add(sum(flows[i]) == need)
    for j, cash in enumerate(supply):
        model.add(sum(flows[i][j] for i in range(len(demand))) == cash)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    solutions = []
    for _ in range(2):
        status = solver.solve(model)
        assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
        values = [[solver.value(variable) for variable in row] for row in flows]
        assert [sum(row) for row in values] == list(demand)
        assert [sum(values[i][j] for i in range(2)) for j in range(2)] == list(supply)
        solutions.append(values)
        model.add_forbidden_assignments(
            [variable for row in flows for variable in row], [[value for row in values for value in row]]
        )
    assert solutions[0] != solutions[1]
    return {
        "relation": "M:N",
        "feasible_examples": solutions,
        "auto_confirm": False,
        "interpretation": "Feasible integer conservation is not identity evidence",
    }


def evaluate(repeats: int) -> dict:
    rows = []
    for case in cases():
        oracle = oracle_subsets(case) if len(case.amounts) <= 24 else None
        if oracle is None:
            assert len(set(case.amounts)) == 1 and case.target % case.amounts[0] == 0
            count = case.target // case.amounts[0]
            oracle_count = math.comb(len(case.amounts), count) if 2 <= count <= case.max_size else 0
        else:
            oracle_count = len(oracle)
        methods = {}
        for name, method in (("bounded", bounded), ("cp_sat", cp_subsets)):
            method(case)
            seconds, peaks = [], []
            for _ in range(repeats):
                tracemalloc.start()
                started = time.perf_counter()
                result = method(case)
                seconds.append(time.perf_counter() - started)
                peaks.append(tracemalloc.get_traced_memory()[1])
                tracemalloc.stop()
            found = {tuple(subset) for subset in result["solutions"]}
            assert all(sum(case.amounts[i] for i in subset) == case.target for subset in found)
            if oracle is not None:
                assert found <= oracle
                if result["complete"]:
                    assert found == oracle
            methods[name] = {
                **result,
                "recall": len(found) / oracle_count if oracle_count else None,
                "median_seconds": statistics.median(seconds),
                "seconds": seconds,
                "peak_python_bytes": max(peaks),
            }
        rows.append({"case": asdict(case), "oracle_solution_count": oracle_count, "methods": methods})
    return {
        "seed": 42,
        "repeats": repeats,
        "ortools": importlib.metadata.version("ortools"),
        "case_hash": hashlib.sha256(
            json.dumps([asdict(case) for case in cases()], sort_keys=True).encode()
        ).hexdigest(),
        "cases": rows,
        "many_to_many": flow_example(),
        "runtime_auto_confirm_policy_changed": False,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    result = evaluate(args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "cases": len(result["cases"]), "case_hash": result["case_hash"]}))


if __name__ == "__main__":
    main()
