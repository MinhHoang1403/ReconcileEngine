from pathlib import Path

from smartrecon.domain.statuses import AmountBasis, Currency, Direction, OrderStatus, Severity
from smartrecon.ingest.mapping import MappingConfig
from smartrecon.ingest.normalization import normalize_bundle
from smartrecon.ingest.readers import read_source_bundle


def _bundle(tmp_path: Path, order_rows: str, bank_rows: str):
    orders_path = tmp_path / "orders.csv"
    bank_path = tmp_path / "bank.csv"
    orders_path.write_text(order_rows, encoding="utf-8")
    bank_path.write_text(bank_rows, encoding="utf-8")
    return read_source_bundle(orders_path=orders_path, bank_path=bank_path)


def _mapping(**overrides) -> MappingConfig:
    values = {
        "order_columns": {
            "order_id": "order_id",
            "ordered_at": "ordered_at",
            "expected_amount": "expected_amount",
        },
        "bank_columns": {
            "bank_txn_id": "bank_txn_id",
            "txn_date": "txn_date",
            "posted_amount": "posted_amount",
            "direction": "direction",
            "amount_basis": "amount_basis",
        },
        "currency": Currency.VND,
    }
    values.update(overrides)
    return MappingConfig(**values)


def _blocking_codes(normalized) -> set[str]:
    return {issue.code for issue in normalized.issues if issue.severity is Severity.BLOCKING}


def test_auto_date_accepts_unambiguous_iso_and_year_first_slashes(tmp_path: Path) -> None:
    raw = _bundle(
        tmp_path,
        "order_id,ordered_at,expected_amount\nO-1,2026/10/17,1000\n",
        "bank_txn_id,txn_date,posted_amount,direction,amount_basis\nB-1,2026-10-18T01:02:03,1000,CREDIT,POSTED_CASH\n",
    )

    normalized = normalize_bundle(raw, _mapping(date_format="AUTO"))

    assert not _blocking_codes(normalized)
    assert normalized.orders[0].ordered_at.isoformat() == "2026-10-17"
    assert normalized.bank_transactions[0].txn_date.isoformat() == "2026-10-18"


def test_auto_date_blocks_ambiguous_day_month_with_exact_source_row(tmp_path: Path) -> None:
    raw = _bundle(
        tmp_path,
        "order_id,ordered_at,expected_amount\nO-1,01/02/2026,1000\n",
        "bank_txn_id,txn_date,posted_amount,direction,amount_basis\nB-1,2026-02-01,1000,CREDIT,POSTED_CASH\n",
    )

    normalized = normalize_bundle(raw, _mapping(date_format="AUTO"))

    issue = next(issue for issue in normalized.issues if issue.code == "ORDER_PARSE_ERROR")
    assert issue.severity is Severity.BLOCKING
    assert issue.source_rows == (2,)
    assert "mơ hồ" in issue.message_vi


def test_each_feed_can_use_a_separate_explicit_date_format(tmp_path: Path) -> None:
    raw = _bundle(
        tmp_path,
        "order_id,ordered_at,expected_amount\nO-1,17/10/2026,1000\n",
        "bank_txn_id,txn_date,posted_amount,direction,amount_basis\nB-1,2026-10-18,1000,CREDIT,POSTED_CASH\n",
    )

    normalized = normalize_bundle(
        raw,
        _mapping(order_date_format="%d/%m/%Y", bank_date_format="%Y-%m-%d"),
    )

    assert not _blocking_codes(normalized)
    assert normalized.orders[0].ordered_at.day == 17
    assert normalized.bank_transactions[0].txn_date.day == 18


def test_split_credit_debit_columns_derive_amount_and_direction(tmp_path: Path) -> None:
    raw = _bundle(
        tmp_path,
        "order_id,ordered_at,expected_amount\nO-1,2026-10-17,1000\n",
        "bank_txn_id,txn_date,credit,debit,amount_basis\n"
        "B-1,2026-10-18,1000,,POSTED_CASH\n"
        "B-2,2026-10-19,,250,POSTED_CASH\n",
    )
    mapping = _mapping(
        bank_columns={
            "bank_txn_id": "bank_txn_id",
            "txn_date": "txn_date",
            "amount_basis": "amount_basis",
        },
        bank_transformations={
            "cash_movement": {
                "type": "SPLIT_CREDIT_DEBIT",
                "credit_column": "credit",
                "debit_column": "debit",
            }
        },
    )

    normalized = normalize_bundle(raw, mapping)

    assert not _blocking_codes(normalized)
    assert [(row.posted_amount_minor, row.direction) for row in normalized.bank_transactions] == [
        (1000, Direction.CREDIT),
        (250, Direction.DEBIT),
    ]


def test_split_credit_debit_blocks_rows_with_two_nonzero_sides(tmp_path: Path) -> None:
    raw = _bundle(
        tmp_path,
        "order_id,ordered_at,expected_amount\nO-1,2026-10-17,1000\n",
        "bank_txn_id,txn_date,credit,debit,amount_basis\nB-1,2026-10-18,1000,100,POSTED_CASH\n",
    )
    mapping = _mapping(
        bank_columns={
            "bank_txn_id": "bank_txn_id",
            "txn_date": "txn_date",
            "amount_basis": "amount_basis",
        },
        bank_transformations={
            "cash_movement": {
                "type": "SPLIT_CREDIT_DEBIT",
                "credit_column": "credit",
                "debit_column": "debit",
            }
        },
    )

    normalized = normalize_bundle(raw, mapping)

    issue = next(issue for issue in normalized.issues if issue.code == "BANK_PARSE_ERROR")
    assert issue.source_rows == (2,)
    assert issue.sample_values == ("1000", "100")
    assert not normalized.bank_transactions


def test_signed_amount_requires_an_explicit_transformation(tmp_path: Path) -> None:
    raw = _bundle(
        tmp_path,
        "order_id,ordered_at,expected_amount\nO-1,2026-10-17,1000\n",
        "bank_txn_id,txn_date,posted_amount,direction,amount_basis\nB-1,2026-10-18,-250,CREDIT,POSTED_CASH\n",
    )
    direct = _mapping(
        bank_columns={
            "bank_txn_id": "bank_txn_id",
            "txn_date": "txn_date",
            "posted_amount": "posted_amount",
            "direction": "direction",
            "amount_basis": "amount_basis",
        },
    )
    explicit = _mapping(
        bank_columns={
            "bank_txn_id": "bank_txn_id",
            "txn_date": "txn_date",
            "amount_basis": "amount_basis",
        },
        bank_transformations={
            "cash_movement": {
                "type": "SIGNED_AMOUNT",
                "source_column": "posted_amount",
                "positive_direction": "CREDIT",
            }
        },
    )

    blocked = normalize_bundle(raw, direct)
    normalized = normalize_bundle(raw, explicit)

    assert "BANK_PARSE_ERROR" in _blocking_codes(blocked)
    assert not _blocking_codes(normalized)
    assert normalized.bank_transactions[0].posted_amount_minor == 250
    assert normalized.bank_transactions[0].direction is Direction.DEBIT


def test_categorical_values_are_converted_only_by_an_explicit_value_map(tmp_path: Path) -> None:
    raw = _bundle(
        tmp_path,
        "order_id,ordered_at,expected_amount,status\nO-1,2026-10-17,1000,Đã giao\n",
        "bank_txn_id,txn_date,posted_amount,direction,amount_basis\nB-1,2026-10-18,1000,CR,Tiền đã ghi sổ\n",
    )
    base = _mapping(
        order_columns={
            "order_id": "order_id",
            "ordered_at": "ordered_at",
            "expected_amount": "expected_amount",
            "order_status": "status",
        }
    )
    explicit = _mapping(
        order_columns=base.order_columns,
        order_transformations={"order_status": {"type": "VALUE_MAP", "values": {"Đã giao": "ELIGIBLE"}}},
        bank_transformations={
            "direction": {"type": "VALUE_MAP", "values": {"CR": "CREDIT"}},
            "amount_basis": {
                "type": "VALUE_MAP",
                "values": {"Tiền đã ghi sổ": "POSTED_CASH"},
            },
        },
    )

    blocked = normalize_bundle(raw, base)
    normalized = normalize_bundle(raw, explicit)

    assert {"ORDER_PARSE_ERROR", "BANK_PARSE_ERROR"} <= _blocking_codes(blocked)
    assert not _blocking_codes(normalized)
    assert normalized.orders[0].order_status is OrderStatus.ELIGIBLE
    assert normalized.bank_transactions[0].direction is Direction.CREDIT


def test_money_separator_and_amount_basis_decisions_remain_explicit(tmp_path: Path) -> None:
    raw = _bundle(
        tmp_path,
        'order_id,ordered_at,expected_amount\nO-1,2026-10-17,"1,234"\n',
        'bank_txn_id,txn_date,posted_amount,direction,amount_basis\nB-1,2026-10-18,"1,234",CREDIT,GROSS_SETTLEMENT\n',
    )
    thousands = _mapping(decimal_separator=".", thousand_separator=",")
    decimal = _mapping(decimal_separator=",", thousand_separator=None)

    accepted = normalize_bundle(raw, thousands)
    rejected = normalize_bundle(raw, decimal)

    assert accepted.orders[0].expected_amount_minor == 1234
    assert accepted.bank_transactions[0].amount_basis is AmountBasis.GROSS_SETTLEMENT
    assert "GROSS_NOT_POSTED_CASH" in _blocking_codes(accepted)
    assert {"ORDER_PARSE_ERROR", "BANK_PARSE_ERROR"} <= _blocking_codes(rejected)


def test_normalization_is_deterministic_and_never_synthesizes_missing_bank_ids(tmp_path: Path) -> None:
    raw = _bundle(
        tmp_path,
        "order_id,ordered_at,expected_amount\nO-1,2026-10-17,1000\n",
        "bank_txn_id,txn_date,posted_amount,direction,amount_basis\n,2026-10-18,1000,CREDIT,NET_SETTLEMENT\n",
    )
    mapping = _mapping()

    first = normalize_bundle(raw, mapping)
    second = normalize_bundle(raw, mapping)

    assert first == second
    assert not first.bank_transactions
    assert "BANK_PARSE_ERROR" in _blocking_codes(first)
