"""Typed reconciliation policies; thresholds are explicit demo heuristics."""

from dataclasses import dataclass

from smartrecon.domain.statuses import Currency


@dataclass(frozen=True, slots=True)
class ReconciliationPolicy:
    currency: Currency
    max_days_diff: int = 3
    fuzzy_candidate_threshold: float = 85.0
    max_candidates_per_item: int = 5
    max_group_orders: int = 3
    max_split_bank_rows: int = 3
    max_group_block_size: int = 20
    max_combinations_per_case: int = 2_000
    allow_verified_psp_fees: bool = True
    rule_version: str = "2026-10-15"

    def __post_init__(self) -> None:
        if self.max_days_diff < 0:
            raise ValueError("max_days_diff không được âm")
        if not 0 <= self.fuzzy_candidate_threshold <= 100:
            raise ValueError("fuzzy_candidate_threshold phải trong [0, 100]")
        if not 2 <= self.max_group_orders <= 4:
            raise ValueError("max_group_orders phải trong [2, 4]")
        if not 2 <= self.max_split_bank_rows <= 4:
            raise ValueError("max_split_bank_rows phải trong [2, 4]")
