import pandas as pd

from smartrecon.ingest.mapping import BANK_REQUIRED, ORDER_REQUIRED, analyze_mapping


def _suggestion(analysis, target: str):
    return next(item for item in analysis.suggestions if item.canonical_target == target)


def test_vietnamese_receivable_aliases_are_auto_selected_with_reasons() -> None:
    frame = pd.DataFrame(
        {
            "Mã ĐH": ["00001", "00002", "00003"],
            "Ngày tạo": ["15/10/2026", "16/10/2026", "17/10/2026"],
            "Thành tiền": ["100000", "250000", "500000"],
        }
    )

    analysis = analyze_mapping(
        frame,
        ORDER_REQUIRED,
        feed="orders",
        required_fields=ORDER_REQUIRED,
    )

    assert analysis.required_auto_selected == 3
    assert analysis.selected_mapping == {
        "expected_amount": "Thành tiền",
        "order_id": "Mã ĐH",
        "ordered_at": "Ngày tạo",
    }
    order_id = _suggestion(analysis, "order_id")
    assert order_id.confidence == "HIGH"
    assert order_id.status == "auto-selected"
    assert order_id.sample_before[0] == "00001"
    assert any("đồng nghĩa" in reason for reason in order_id.reasons)


def test_english_bank_aliases_rank_correct_semantics() -> None:
    frame = pd.DataFrame(
        {
            "Transaction No": ["T1", "T2"],
            "Posting Date": ["2026-10-15", "2026-10-16"],
            "Credit Amount": ["1000.00", "2000.00"],
            "Transaction Memo": ["ORDER A", "ORDER B"],
        }
    )

    analysis = analyze_mapping(
        frame,
        {"bank_txn_id", "txn_date", "posted_amount", "description"},
        feed="bank_transactions",
        required_fields={"bank_txn_id", "txn_date", "posted_amount"},
    )

    assert analysis.selected_mapping["bank_txn_id"] == "Transaction No"
    assert analysis.selected_mapping["txn_date"] == "Posting Date"
    assert analysis.selected_mapping["posted_amount"] == "Credit Amount"
    assert analysis.selected_mapping["description"] == "Transaction Memo"


def test_competing_amount_columns_are_never_randomly_auto_selected() -> None:
    frame = pd.DataFrame(
        {
            "Amount Due": ["100000", "200000"],
            "Balance Due": ["100000", "200000"],
        }
    )

    analysis = analyze_mapping(
        frame,
        {"expected_amount"},
        feed="orders",
        required_fields={"expected_amount"},
    )
    suggestion = _suggestion(analysis, "expected_amount")

    assert suggestion.status == "needs-review"
    assert suggestion.source_column == "Amount Due"
    assert suggestion.competitors[0].source_column == "Balance Due"
    assert "expected_amount" not in analysis.selected_mapping


def test_ambiguous_day_month_value_requires_review_even_with_clear_name() -> None:
    frame = pd.DataFrame({"Created Date": ["01/02/2026", "03/04/2026"]})

    analysis = analyze_mapping(
        frame,
        {"ordered_at"},
        feed="orders",
        required_fields={"ordered_at"},
    )
    suggestion = _suggestion(analysis, "ordered_at")

    assert suggestion.status == "needs-review"
    assert any("locale" in reason for reason in suggestion.reasons)


def test_profile_mapping_has_priority_but_only_for_existing_column() -> None:
    frame = pd.DataFrame({"Mã nguồn": ["A-1", "A-2"], "Cột khác": ["x", "y"]})

    analysis = analyze_mapping(
        frame,
        {"bank_txn_id", "txn_date"},
        feed="bank_transactions",
        required_fields={"bank_txn_id", "txn_date"},
        profile_mapping={"bank_txn_id": "Mã nguồn", "txn_date": "Không tồn tại"},
    )

    bank_id = _suggestion(analysis, "bank_txn_id")
    missing_date = _suggestion(analysis, "txn_date")
    assert bank_id.status == "auto-selected"
    assert bank_id.source_column == "Mã nguồn"
    assert any("profile" in reason for reason in bank_id.reasons)
    assert missing_date.status == "unsupported"


def test_selected_mapping_never_reuses_one_source_column() -> None:
    frame = pd.DataFrame({"Reference": ["R1", "R2"]})

    analysis = analyze_mapping(
        frame,
        {"txn_ref", "bank_txn_id"},
        feed="bank_transactions",
        required_fields=set(),
    )

    assert len(set(analysis.selected_mapping.values())) == len(analysis.selected_mapping)


def test_required_field_without_semantic_or_type_evidence_is_unsupported() -> None:
    frame = pd.DataFrame({"Ghi chú nội bộ": ["alpha", "beta"]})

    analysis = analyze_mapping(
        frame,
        BANK_REQUIRED,
        feed="bank_transactions",
        required_fields=BANK_REQUIRED,
    )

    assert analysis.required_unsupported >= 3
    assert not {"txn_date", "posted_amount", "direction", "amount_basis"} & analysis.selected_mapping.keys()


def test_explicit_credit_debit_pair_is_suggested_as_a_traceable_transformation() -> None:
    frame = pd.DataFrame(
        {
            "Mã giao dịch": ["T1", "T2"],
            "Ngày giao dịch": ["2026-10-16", "2026-10-17"],
            "Ghi có": ["1000", ""],
            "Ghi nợ": ["", "250"],
            "Cơ sở số tiền": ["POSTED_CASH", "POSTED_CASH"],
        }
    )

    analysis = analyze_mapping(
        frame,
        BANK_REQUIRED,
        feed="bank_transactions",
        required_fields=BANK_REQUIRED,
    )

    specification = analysis.selected_transformations["cash_movement"]
    assert specification == {
        "type": "SPLIT_CREDIT_DEBIT",
        "credit_column": "Ghi có",
        "debit_column": "Ghi nợ",
    }
    for target in ("posted_amount", "direction"):
        suggestion = _suggestion(analysis, target)
        assert suggestion.status == "auto-selected"
        assert suggestion.transformation == specification
        assert suggestion.source_column is None
