"""Health Gate projection and auditable row-exclusion resolution."""

from dataclasses import dataclass

from smartrecon.domain.statuses import Severity
from smartrecon.ingest.normalization import DataIssue, NormalizedBundle


@dataclass(frozen=True, slots=True)
class Exclusion:
    feed: str
    source_row_number: int
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("Loại trừ dòng bắt buộc có lý do")


@dataclass(frozen=True, slots=True)
class HealthReport:
    status: str
    blocking_count: int
    warning_count: int
    info_count: int
    issues: tuple[DataIssue, ...]
    excluded_rows: tuple[Exclusion, ...] = ()


def build_health_report(normalized: NormalizedBundle, excluded_rows: tuple[Exclusion, ...] = ()) -> HealthReport:
    """Project severity counts; only unresolved blocking issues close the gate."""
    excluded_keys = {(item.feed, item.source_row_number) for item in excluded_rows}
    effective_issues: list[DataIssue] = []
    for issue in normalized.issues:
        if issue.source_rows and all((issue.feed, row_number) in excluded_keys for row_number in issue.source_rows):
            continue
        effective_issues.append(issue)

    blocking = sum(issue.severity is Severity.BLOCKING for issue in effective_issues)
    warnings = sum(issue.severity is Severity.WARNING for issue in effective_issues)
    info = sum(issue.severity is Severity.INFO for issue in effective_issues)
    return HealthReport(
        status="BLOCKED" if blocking else "READY",
        blocking_count=blocking,
        warning_count=warnings,
        info_count=info,
        issues=tuple(effective_issues),
        excluded_rows=excluded_rows,
    )


def apply_exclusions(
    normalized: NormalizedBundle, exclusions: list[Exclusion]
) -> tuple[NormalizedBundle, HealthReport]:
    """Exclude canonical rows only by explicit source row and recorded reason."""
    keys = {(item.feed, item.source_row_number) for item in exclusions}
    orders = tuple(
        order
        for order in normalized.orders
        if order.lineage is None or ("orders", order.lineage.source_row_number) not in keys
    )
    banks = tuple(
        bank
        for bank in normalized.bank_transactions
        if bank.lineage is None or ("bank_transactions", bank.lineage.source_row_number) not in keys
    )
    resolved = NormalizedBundle(
        orders,
        banks,
        normalized.issues,
        normalized.rejected_rows,
        tuple(
            bank_id for bank_id in normalized.duplicate_bank_ids if any(bank.bank_txn_id == bank_id for bank in banks)
        ),
        normalized.source_hashes,
    )
    exclusion_tuple = tuple(exclusions)
    return resolved, build_health_report(resolved, exclusion_tuple)
