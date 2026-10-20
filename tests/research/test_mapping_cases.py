"""Independent mapping answers are shared by the regression suite and research runner."""

import pytest

from research.mapping_cases import mapping_cases
from smartrecon.ingest.mapping import BANK_FIELDS, BANK_REQUIRED, ORDER_FIELDS, ORDER_REQUIRED, analyze_mapping


@pytest.mark.parametrize("case", mapping_cases(), ids=lambda case: case.name)
def test_independent_mapping_answers(case) -> None:
    targets, required = (ORDER_FIELDS, ORDER_REQUIRED) if case.feed == "orders" else (BANK_FIELDS, BANK_REQUIRED)
    analysis = analyze_mapping(
        case.frame, targets, feed=case.feed, required_fields=required, profile_mapping=case.profile
    )
    assert analysis.selected_mapping == case.expected
    assert analysis.selected_transformations == case.transformations
    assert not set(case.abstain) & analysis.selected_mapping.keys()
    assert len(analysis.selected_mapping.values()) == len(set(analysis.selected_mapping.values()))
