from pathlib import Path

from smartrecon.ingest.profiles import recognize_profiles, schema_fingerprint
from smartrecon.ingest.readers import read_source_bundle


def _bundle(tmp_path: Path, orders: str, bank: str):
    orders_path = tmp_path / "orders.csv"
    bank_path = tmp_path / "bank.csv"
    orders_path.write_text(orders, encoding="utf-8")
    bank_path.write_text(bank, encoding="utf-8")
    return read_source_bundle(orders_path=orders_path, bank_path=bank_path)


def test_generic_receivable_and_split_bank_profiles_are_recognized(tmp_path: Path) -> None:
    raw = _bundle(
        tmp_path,
        "Mã ĐH,Ngày tạo,Thành tiền\nO-1,2026-10-17,1000\n",
        "Mã giao dịch,Ngày giao dịch,Ghi có,Ghi nợ,Cơ sở số tiền\nB-1,2026-10-18,1000,,POSTED_CASH\n",
    )

    profiles = recognize_profiles(raw)

    assert profiles["orders"]["key"] == "GENERIC_RECEIVABLE"
    assert profiles["orders"]["status"] == "RECOGNIZED"
    assert profiles["bank_transactions"]["key"] == "GENERIC_SPLIT_BANK_STATEMENT"
    assert profiles["bank_transactions"]["status"] == "RECOGNIZED"


def test_psp_profile_requires_an_explicit_net_amount_basis(tmp_path: Path) -> None:
    raw = _bundle(
        tmp_path,
        "order_id,ordered_at,expected_amount\nO-1,2026-10-17,1000\n",
        "bank_txn_id,txn_date,posted_amount,direction,amount_basis\nB-1,2026-10-18,950,CREDIT,NET_SETTLEMENT\n",
    )

    profile = recognize_profiles(raw)["bank_transactions"]

    assert profile["key"] == "PSP_NET_SETTLEMENT"
    assert "NET_SETTLEMENT" in profile["reasons"][0]


def test_shopee_order_and_payout_shapes_are_kept_distinct(tmp_path: Path) -> None:
    order_level = _bundle(
        tmp_path,
        "shopee_order_id,Ngày tạo,Thành tiền\nS-1,2026-10-17,1000\n",
        "bank_txn_id,txn_date,posted_amount,direction,amount_basis\nB-1,2026-10-18,1000,CREDIT,POSTED_CASH\n",
    )
    payout_dir = tmp_path / "payout"
    payout_dir.mkdir()
    payout_level = _bundle(
        payout_dir,
        "shopee_payout_id,settlement_id,settlement_amount\nP-1,SET-1,950\n",
        "bank_txn_id,txn_date,posted_amount,direction,amount_basis\nB-1,2026-10-18,950,CREDIT,POSTED_CASH\n",
    )

    order_profile = recognize_profiles(order_level)["orders"]
    payout_profile = recognize_profiles(payout_level)["orders"]

    assert order_profile["key"] == "SHOPEE_ORDER_LEVEL"
    assert order_profile["status"] == "NEEDS_REVIEW"
    assert payout_profile["key"] == "SHOPEE_PAYOUT_REVIEW_REQUIRED"
    assert payout_profile["status"] == "UNSUPPORTED_AUTOMATIC_AGGREGATION"


def test_schema_fingerprint_changes_for_header_or_structure_drift(tmp_path: Path) -> None:
    original = _bundle(
        tmp_path,
        "order_id,ordered_at,expected_amount\nO-1,2026-10-17,1000\n",
        "bank_txn_id,txn_date,posted_amount,direction,amount_basis\nB-1,2026-10-18,1000,CREDIT,POSTED_CASH\n",
    )
    changed_dir = tmp_path / "changed"
    changed_dir.mkdir()
    changed = _bundle(
        changed_dir,
        "order_id,ordered_at,amount_due\nO-1,2026-10-17,1000\n",
        "bank_txn_id,txn_date,posted_amount,direction,amount_basis\nB-1,2026-10-18,1000,CREDIT,POSTED_CASH\n",
    )

    assert schema_fingerprint(original) == schema_fingerprint(original)
    assert schema_fingerprint(original) != schema_fingerprint(changed)
