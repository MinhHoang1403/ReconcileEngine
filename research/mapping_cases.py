"""Independent synthetic schema answers; this module never imports a mapping implementation."""

from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True)
class MappingCase:
    name: str
    feed: str
    columns: dict[str, list]
    expected: dict[str, str]
    abstain: tuple[str, ...] = ()
    transformations: dict = field(default_factory=dict)
    profile: dict[str, str] | None = None
    split: str = "development"

    @property
    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.columns)


def mapping_cases() -> tuple[MappingCase, ...]:
    """State semantic decisions before running any tested method; abstention is an answer."""
    return (
        MappingCase(
            "canonical",
            "orders",
            {
                "order_id": ["001", "002"],
                "ordered_at": ["2026-10-16", "2026-10-17"],
                "expected_amount": ["100000", "200000"],
            },
            {"order_id": "order_id", "ordered_at": "ordered_at", "expected_amount": "expected_amount"},
        ),
        MappingCase(
            "vietnamese",
            "orders",
            {
                "Mã ĐH": ["001", "002"],
                "Ngày tạo": ["16/10/2026", "17/10/2026"],
                "Số tiền phải thu": ["100000", "200000"],
            },
            {"order_id": "Mã ĐH", "ordered_at": "Ngày tạo", "expected_amount": "Số tiền phải thu"},
        ),
        MappingCase(
            "unaccented",
            "orders",
            {
                "ma don hang": ["DH01", "DH02"],
                "ngay phat sinh": ["2026-10-16", "2026-10-17"],
                "so tien can thu": ["100000", "200000"],
            },
            {"order_id": "ma don hang", "ordered_at": "ngay phat sinh", "expected_amount": "so tien can thu"},
        ),
        MappingCase(
            "english",
            "orders",
            {
                "SO Number": ["S01", "S02"],
                "Created Date": ["2026-10-16", "2026-10-17"],
                "Amount Due": ["100000", "200000"],
            },
            {"order_id": "SO Number", "ordered_at": "Created Date", "expected_amount": "Amount Due"},
        ),
        MappingCase(
            "mixed",
            "orders",
            {
                "Mã ĐH": ["01", "02"],
                "Created Date": ["2026-10-16", "2026-10-17"],
                "Thành tiền": ["100000", "200000"],
            },
            {"order_id": "Mã ĐH", "ordered_at": "Created Date", "expected_amount": "Thành tiền"},
        ),
        MappingCase(
            "bank_abbreviations",
            "bank_transactions",
            {
                "TX ID": ["T01", "T02"],
                "Posting Date": ["2026-10-16", "2026-10-17"],
                "Credit Amount": ["100000", "200000"],
                "CCY": ["VND", "VND"],
                "Credit Debit": ["CREDIT", "DEBIT"],
                "Basis": ["POSTED_CASH", "POSTED_CASH"],
            },
            {
                "bank_txn_id": "TX ID",
                "txn_date": "Posting Date",
                "posted_amount": "Credit Amount",
                "currency": "CCY",
                "direction": "Credit Debit",
                "amount_basis": "Basis",
            },
        ),
        MappingCase(
            "two_receivable_amounts",
            "orders",
            {
                "Amount Due": ["100000", "200000"],
                "Balance Due": ["100000", "200000"],
            },
            {},
            ("expected_amount",),
        ),
        MappingCase("ambiguous_dates", "orders", {"ordered_at": ["01/02/2026", "03/04/2026"]}, {}, ("ordered_at",)),
        MappingCase(
            "ambiguous_separators", "orders", {"expected_amount": ["1,234", "2,345"]}, {}, ("expected_amount",)
        ),
        MappingCase("empty_amount", "orders", {"expected_amount": ["", "", ""]}, {}, ("expected_amount",)),
        MappingCase(
            "wrong_semantics", "orders", {"expected_amount": ["cash pending", "not yet paid"]}, {}, ("expected_amount",)
        ),
        MappingCase(
            "first_five_valid",
            "orders",
            {"expected_amount": ["100000"] * 5 + ["bad value"] * 25},
            {},
            ("expected_amount",),
        ),
        MappingCase(
            "profile_drift",
            "orders",
            {"Collected": ["gross report", "gross report"]},
            {},
            ("expected_amount",),
            profile={"expected_amount": "Collected"},
        ),
        MappingCase(
            "signed_cash_without_convention",
            "bank_transactions",
            {"posted_amount": ["100000", "-200000"]},
            {},
            ("posted_amount", "direction"),
        ),
        MappingCase(
            "gross_net",
            "bank_transactions",
            {
                "Gross Amount": ["100000", "200000"],
                "Net Amount": ["98000", "196000"],
                "Fee Amount": ["2000", "4000"],
                "amount_basis": ["NET_SETTLEMENT", "NET_SETTLEMENT"],
            },
            {"posted_amount": "Net Amount", "declared_fee": "Fee Amount", "amount_basis": "amount_basis"},
        ),
        MappingCase("gross_only", "bank_transactions", {"Gross Amount": ["100000", "200000"]}, {}, ("posted_amount",)),
        MappingCase(
            "shopee_order_level",
            "orders",
            {
                "Mã đơn hàng": ["SP001", "SP002"],
                "Ngày tạo": ["2026-10-16", "2026-10-17"],
                "Số tiền phải thu": ["100000", "200000"],
                "shopee_order_id": ["SP001", "SP002"],
            },
            {"order_id": "Mã đơn hàng", "ordered_at": "Ngày tạo", "expected_amount": "Số tiền phải thu"},
        ),
        MappingCase(
            "split_credit_debit",
            "bank_transactions",
            {
                "bank_txn_id": ["B1", "B2"],
                "txn_date": ["2026-10-16", "2026-10-17"],
                "credit": ["1000", ""],
                "debit": ["", "250"],
                "amount_basis": ["POSTED_CASH", "POSTED_CASH"],
            },
            {"bank_txn_id": "bank_txn_id", "txn_date": "txn_date", "amount_basis": "amount_basis"},
            transformations={
                "cash_movement": {"type": "SPLIT_CREDIT_DEBIT", "credit_column": "credit", "debit_column": "debit"}
            },
        ),
        MappingCase("unnamed", "orders", {"Cột chưa đặt tên 1": ["100000", "200000"]}, {}, ("expected_amount",)),
        MappingCase(
            "shopee_payout_level",
            "orders",
            {
                "Shopee payout ID": ["PAY01", "PAY02"],
                "settlement_amount": ["100000", "200000"],
            },
            {},
            ("order_id", "expected_amount"),
        ),
        MappingCase(
            "zero_prefix_id", "orders", {"order_id": ["00001", "00002"]}, {"order_id": "order_id"}, split="holdout"
        ),
        MappingCase(
            "holdout_bad_tail",
            "orders",
            {"Amount Due": ["1000"] * 101 + ["invalid"] * 30},
            {},
            ("expected_amount",),
            split="holdout",
        ),
        MappingCase(
            "holdout_wrong_date", "orders", {"ordered_at": ["red", "blue"]}, {}, ("ordered_at",), split="holdout"
        ),
        MappingCase(
            "holdout_vietnamese_bank",
            "bank_transactions",
            {
                "Mã giao dịch": ["GD001", "GD002"],
                "Ngày hạch toán": ["2026-10-16", "2026-10-17"],
                "Số tiền thực nhận": ["450000", "780000"],
                "Chiều giao dịch": ["CREDIT", "CREDIT"],
            },
            {
                "bank_txn_id": "Mã giao dịch",
                "txn_date": "Ngày hạch toán",
                "posted_amount": "Số tiền thực nhận",
                "direction": "Chiều giao dịch",
            },
            split="holdout",
        ),
    )
