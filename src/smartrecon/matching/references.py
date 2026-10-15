"""Reference normalization and boundary-safe extraction against known IDs."""

import re
import unicodedata
from collections.abc import Sequence
from re import Pattern

from smartrecon.domain.models import Order


def compact_reference(value: str) -> str:
    """Build a comparison key without converting look-alike characters."""
    normalized = unicodedata.normalize("NFKC", value).upper()
    return "".join(character for character in normalized if character.isalnum())


def order_reference_index(orders: list[Order]) -> dict[str, tuple[str, ...]]:
    """Map compact refs to all owning orders so collisions remain visible."""
    owners: dict[str, set[str]] = {}
    for order in orders:
        for value in (order.order_id, order.external_ref):
            if not value:
                continue
            compact = compact_reference(value)
            if compact:
                owners.setdefault(compact, set()).add(order.order_id)
    return {reference: tuple(sorted(order_ids)) for reference, order_ids in owners.items()}


def compile_known_reference_patterns(known_references: set[str]) -> tuple[tuple[str, Pattern[str]], ...]:
    """Compile boundary-safe patterns once for reuse across all bank rows in a run."""
    patterns: list[tuple[str, Pattern[str]]] = []
    for reference in sorted(known_references, key=lambda item: (-len(item), item)):
        flexible = r"[\s_-]*".join(re.escape(character) for character in reference)
        patterns.append((reference, re.compile(rf"(?<![A-Z0-9]){flexible}(?![A-Z0-9])")))
    return tuple(patterns)


def extract_known_references(
    text: str,
    known_references: set[str],
    *,
    compiled_patterns: Sequence[tuple[str, Pattern[str]]] | None = None,
) -> tuple[str, ...]:
    """Return full known references with strict alphanumeric token boundaries."""
    normalized = unicodedata.normalize("NFKC", text).upper()
    hits: list[str] = []
    patterns = compiled_patterns or compile_known_reference_patterns(known_references)
    for reference, pattern in patterns:
        if pattern.search(normalized):
            hits.append(reference)
    return tuple(hits)


def fuzzy_text(value: str | None) -> str:
    """Normalize text for ranking while preserving the original evidence elsewhere."""
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())
