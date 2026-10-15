"""Framework-independent domain records for reconciliation."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from smartrecon.domain.statuses import (
    AmountBasis,
    Currency,
    Direction,
    GroupType,
    LinkStatus,
    OrderStatus,
    PaymentStatus,
    ReviewStatus,
)


@dataclass(frozen=True, slots=True)
class SourceLineage:
    """Immutable pointer from a canonical record to its source row."""

    source_file_id: str
    source_row_number: int
    source_row_hash: str


@dataclass(frozen=True, slots=True)
class Order:
    """An eligible or classified internal receivable."""

    order_id: str
    ordered_at: date
    expected_amount_minor: int
    currency: Currency
    order_status: OrderStatus = OrderStatus.ELIGIBLE
    external_ref: str | None = None
    customer_id: str | None = None
    customer_name: str | None = None
    payment_channel: str | None = None
    batch_ref: str | None = None
    description: str | None = None
    lineage: SourceLineage | None = None

    def __post_init__(self) -> None:
        if not self.order_id.strip():
            raise ValueError("order_id không được rỗng")
        if self.expected_amount_minor < 0:
            raise ValueError("expected_amount_minor không được âm")


@dataclass(frozen=True, slots=True)
class BankTransaction:
    """One posted bank or PSP row; direction carries the cash sign."""

    bank_txn_id: str
    txn_date: date
    posted_amount_minor: int
    direction: Direction
    amount_basis: AmountBasis
    currency: Currency
    txn_ref: str | None = None
    value_date: date | None = None
    description: str | None = None
    sender_name: str | None = None
    channel: str | None = None
    batch_ref: str | None = None
    declared_fee_minor: int | None = None
    lineage: SourceLineage | None = None

    def __post_init__(self) -> None:
        if not self.bank_txn_id.strip():
            raise ValueError("bank_txn_id không được rỗng")
        if self.posted_amount_minor < 0:
            raise ValueError("posted_amount_minor là độ lớn và không được âm")
        if self.declared_fee_minor is not None and self.declared_fee_minor < 0:
            raise ValueError("declared_fee_minor không được âm")

    @property
    def eligible_credit_minor(self) -> int:
        """Cash available to matching; gross reports and debits are excluded."""
        if self.direction is not Direction.CREDIT:
            return 0
        if self.amount_basis not in {AmountBasis.POSTED_CASH, AmountBasis.NET_SETTLEMENT}:
            return 0
        return self.posted_amount_minor


@dataclass(frozen=True, slots=True)
class MatchEvidence:
    """Auditable facts supporting a confirmed link or proposal."""

    rule_id: str
    rule_version: str
    reason_codes: tuple[str, ...]
    explanation_vi: str
    reference_hits: tuple[str, ...] = ()
    amount_delta_minor: int | None = None
    date_delta_days: int | None = None
    score: float | None = None
    features: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AllocationEdge:
    """Confirmed cash assigned from one eligible credit to one receivable."""

    edge_id: str
    group_id: str
    order_id: str
    bank_txn_id: str
    allocated_cash_minor: int
    currency: Currency

    def __post_init__(self) -> None:
        if self.allocated_cash_minor < 0:
            raise ValueError("allocated_cash_minor không được âm")


@dataclass(frozen=True, slots=True)
class VerifiedAdjustment:
    """A non-cash receivable adjustment backed by an explicit policy/evidence."""

    adjustment_id: str
    order_id: str
    amount_minor: int
    adjustment_type: str
    evidence_reference: str

    def __post_init__(self) -> None:
        if self.amount_minor < 0:
            raise ValueError("amount_minor không được âm")
        if not self.evidence_reference.strip():
            raise ValueError("Điều chỉnh phải có evidence_reference")


@dataclass(frozen=True, slots=True)
class MatchGroup:
    """A relation group and its evidence; proposals carry no effective cash."""

    group_id: str
    group_type: GroupType
    order_ids: tuple[str, ...]
    bank_txn_ids: tuple[str, ...]
    link_status: LinkStatus
    review_status: ReviewStatus
    payment_statuses: dict[str, PaymentStatus]
    evidence: MatchEvidence


@dataclass(frozen=True, slots=True)
class Candidate:
    """A non-effective candidate shown for analysis or later review."""

    candidate_id: str
    order_ids: tuple[str, ...]
    bank_txn_ids: tuple[str, ...]
    group_type: GroupType
    evidence: MatchEvidence
    competing_candidate_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExceptionCase:
    """An unresolved or risk-bearing business case with retained participants."""

    exception_id: str
    reason_codes: tuple[str, ...]
    order_ids: tuple[str, ...] = ()
    bank_txn_ids: tuple[str, ...] = ()
    risk_amount_minor: int = 0


@dataclass(frozen=True, slots=True)
class RunManifest:
    """Inputs and policy identity needed to reproduce semantic results."""

    dataset_id: str
    currency: Currency
    source_hashes: dict[str, str]
    mapping_hash: str
    policy_hash: str
    rule_version: str
    semantic_checksum: str
