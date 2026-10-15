"""Adapter for user-supplied Olist CSVs; no dataset is downloaded or bundled."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import pandas as pd


class OlistInputError(ValueError):
    """Raised when supplied Olist files do not satisfy the observed schema."""


@dataclass(frozen=True, slots=True)
class OlistDerivedBundle:
    """Observed Olist receivables paired with explicitly synthetic settlements."""

    orders: tuple[dict[str, Any], ...]
    bank_transactions: tuple[dict[str, Any], ...]
    provenance: dict[str, Any]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_columns(frame: pd.DataFrame, required: set[str], source: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise OlistInputError(f"{source} thiếu cột bắt buộc: {', '.join(missing)}")


def prepare_olist_derived_sample(
    orders_path: Path,
    payments_path: Path,
    *,
    seed: int = 42,
    sample_size: int = 100,
) -> OlistDerivedBundle:
    """Build a deterministic sample while labeling every bank row as synthetic.

    Payment rows are aggregated only to create an observed receivable amount for
    the demo. They are not represented as an actual bank statement or PSP report.
    """
    if not orders_path.is_file() or not payments_path.is_file():
        raise OlistInputError("Cần cung cấp hai CSV Olist hợp lệ; adapter không tự tải dữ liệu")

    orders = pd.read_csv(orders_path, dtype="string")
    payments = pd.read_csv(payments_path, dtype={"order_id": "string"})
    _require_columns(
        orders,
        {"order_id", "order_purchase_timestamp", "order_status"},
        orders_path.name,
    )
    _require_columns(payments, {"order_id", "payment_value"}, payments_path.name)

    payment_values = pd.to_numeric(payments["payment_value"], errors="coerce")
    if payment_values.isna().any():
        raise OlistInputError("payment_value chứa giá trị không phải số")
    payments = payments.assign(payment_value=payment_values)
    totals = payments.groupby("order_id", as_index=False)["payment_value"].sum()
    eligible = orders.loc[orders["order_status"].eq("delivered")].merge(totals, on="order_id")
    if len(eligible) < sample_size:
        raise OlistInputError(
            f"Không đủ {sample_size} delivered orders có payment; chỉ có {len(eligible)}"
        )

    selected = eligible.sample(n=sample_size, random_state=seed).sort_values("order_id")
    rng = random.Random(seed)
    canonical_orders: list[dict[str, Any]] = []
    synthetic_bank: list[dict[str, Any]] = []
    for index, row in enumerate(selected.itertuples(index=False), start=1):
        amount_minor = int(
            (Decimal(str(row.payment_value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        ordered_at = pd.Timestamp(row.order_purchase_timestamp)
        canonical_orders.append(
            {
                "order_id": str(row.order_id),
                "ordered_at": ordered_at.isoformat(),
                "expected_amount_minor": amount_minor,
                "currency": "BRL",
                "order_status": "ELIGIBLE",
                "source_semantics": "olist_observed_payment_total",
            }
        )
        lag_days = rng.randrange(0, 4)
        synthetic_bank.append(
            {
                "bank_txn_id": f"SYN-OLIST-{index:05d}",
                "txn_ref": f"SYN-{index:05d}",
                "txn_date": (ordered_at + timedelta(days=lag_days)).date().isoformat(),
                "posted_amount_minor": amount_minor,
                "direction": "CREDIT",
                "amount_basis": "POSTED_CASH",
                "currency": "BRL",
                "description": f"Synthetic settlement {row.order_id}",
                "source_semantics": "synthetic_not_bank_statement",
            }
        )

    provenance = {
        "profile": "olist_derived_demo",
        "seed": seed,
        "source_files": {
            orders_path.name: _file_sha256(orders_path),
            payments_path.name: _file_sha256(payments_path),
        },
        "observed_columns": ["order_id", "order_purchase_timestamp", "payment_value"],
        "synthetic_columns": [
            "bank_txn_id",
            "txn_ref",
            "txn_date",
            "direction",
            "amount_basis",
            "description",
        ],
        "warning": "Bank/PSP feed is synthetic; Olist does not contain a bank statement.",
    }
    return OlistDerivedBundle(tuple(canonical_orders), tuple(synthetic_bank), provenance)
