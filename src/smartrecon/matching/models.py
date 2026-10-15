"""Internal proposal type shared by matching layers and the resolver."""

from dataclasses import dataclass

from smartrecon.domain.models import MatchEvidence
from smartrecon.domain.statuses import GroupType


@dataclass(frozen=True, slots=True)
class ProposedGroup:
    order_ids: tuple[str, ...]
    bank_txn_ids: tuple[str, ...]
    group_type: GroupType
    layer: str
    evidence: MatchEvidence
    auto_confirm: bool

    @property
    def participant_key(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        return self.order_ids, self.bank_txn_ids
