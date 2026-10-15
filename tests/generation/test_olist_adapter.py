from pathlib import Path

import pandas as pd
import pytest

from smartrecon.generation.olist import OlistInputError, prepare_olist_derived_sample


def test_olist_adapter_labels_bank_feed_synthetic(tmp_path: Path) -> None:
    orders_path = tmp_path / "olist_orders_dataset.csv"
    payments_path = tmp_path / "olist_order_payments_dataset.csv"
    pd.DataFrame(
        {
            "order_id": ["olist-a", "olist-b"],
            "order_purchase_timestamp": ["2018-01-01", "2018-01-02"],
            "order_status": ["delivered", "delivered"],
        }
    ).to_csv(orders_path, index=False)
    pd.DataFrame(
        {
            "order_id": ["olist-a", "olist-a", "olist-b"],
            "payment_value": ["10.00", "2.50", "20.00"],
        }
    ).to_csv(payments_path, index=False)

    bundle = prepare_olist_derived_sample(orders_path, payments_path, sample_size=2)

    amounts = {row["order_id"]: row["expected_amount_minor"] for row in bundle.orders}
    assert amounts == {"olist-a": 1250, "olist-b": 2000}
    assert all(row["source_semantics"] == "synthetic_not_bank_statement" for row in bundle.bank_transactions)
    assert bundle.provenance["profile"] == "olist_derived_demo"


def test_olist_adapter_never_silently_invents_missing_source(tmp_path: Path) -> None:
    with pytest.raises(OlistInputError, match="không tự tải"):
        prepare_olist_derived_sample(tmp_path / "missing.csv", tmp_path / "missing2.csv")
