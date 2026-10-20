"""Conservative import handoff: automatic normalization is not financial confirmation."""

import re
from dataclasses import dataclass

from smartrecon.domain.statuses import Currency
from smartrecon.ingest.mapping import MappingAnalysis, MappingConfig
from smartrecon.ingest.normalization import normalize_text
from smartrecon.ingest.readers import RawSourceBundle


@dataclass(frozen=True, slots=True)
class AutomaticImportPlan:
    mapping: MappingConfig | None
    reasons: tuple[str, ...]


def plan_automatic_import(
    raw: RawSourceBundle,
    orders: MappingAnalysis,
    bank: MappingAnalysis,
    *,
    confirmed_mapping: MappingConfig | None = None,
    source_supported: bool = True,
) -> AutomaticImportPlan:
    """Offer only proven columns and explicit parsing conventions to the normalizer.

    A saved profile must already have passed full-row validation by its caller.
    Unconfigured money must be unformatted integer text on EVERY source row;
    accepting `1.000` with a guessed locale can silently change VND by 1000x.
    This helper does not normalize, persist, acknowledge warnings or match rows.
    """
    reasons: list[str] = []
    if any(table.structure.status != "AUTO_SELECTED" for table in (raw.orders, raw.bank_transactions)):
        reasons.append("STRUCTURE_REQUIRES_CONFIRMATION")
    if not source_supported:
        reasons.append("SOURCE_REQUIRES_CONFIRMATION")
    if confirmed_mapping is not None:
        return AutomaticImportPlan(None if reasons else confirmed_mapping, tuple(reasons))
    for analysis in (orders, bank):
        if analysis.required_auto_selected != analysis.required_total:
            reasons.append("MAPPING_REQUIRES_CONFIRMATION")
        if any(
            item.canonical_target in {"ordered_at", "txn_date", "value_date"}
            and item.status != "auto-selected"
            and item.heuristic_score >= 60
            for item in analysis.suggestions
        ):
            reasons.append("DATE_FORMAT_REQUIRES_CONFIRMATION")
        if any(item.status != "auto-selected" and item.heuristic_score >= 60 for item in analysis.suggestions):
            reasons.append("MAPPING_REQUIRES_CONFIRMATION")

    observed_currency: set[str] = set()
    for table, analysis in ((raw.orders, orders), (raw.bank_transactions, bank)):
        source = analysis.selected_mapping.get("currency")
        if source is None:
            reasons.append("CURRENCY_REQUIRES_CONFIRMATION")
        else:
            observed_currency.update(normalize_text(value).upper() for value in table.frame[source].tolist())
        money_sources = {
            source
            for target, source in analysis.selected_mapping.items()
            if target in {"expected_amount", "posted_amount", "declared_fee"}
        }
        split = analysis.selected_transformations.get("cash_movement", {})
        if split.get("type") == "SPLIT_CREDIT_DEBIT":
            money_sources.update((split["credit_column"], split["debit_column"]))
        for source in money_sources:
            if any(
                text and not re.fullmatch(r"\+?\d+", text)
                for value in table.frame[source].tolist()
                if (text := normalize_text(value))
            ):
                reasons.append("MONEY_FORMAT_REQUIRES_CONFIRMATION")
    if len(observed_currency) != 1 or not observed_currency <= {"VND", "BRL"}:
        reasons.append("CURRENCY_REQUIRES_CONFIRMATION")
    if reasons:
        return AutomaticImportPlan(None, tuple(dict.fromkeys(reasons)))
    return AutomaticImportPlan(
        MappingConfig(
            order_columns=dict(orders.selected_mapping),
            bank_columns=dict(bank.selected_mapping),
            currency=Currency(next(iter(observed_currency))),
            date_format="AUTO",
            decimal_separator=".",
            thousand_separator=None,
            confirmed_structure=True,
            order_date_format="AUTO",
            bank_date_format="AUTO",
            order_transformations=dict(orders.selected_transformations),
            bank_transformations=dict(bank.selected_transformations),
        ),
        (),
    )
