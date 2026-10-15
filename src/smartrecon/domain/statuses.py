"""Closed status vocabularies shared by the core and transport schemas."""

from enum import StrEnum


class Currency(StrEnum):
    VND = "VND"
    BRL = "BRL"


class Direction(StrEnum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class AmountBasis(StrEnum):
    POSTED_CASH = "POSTED_CASH"
    NET_SETTLEMENT = "NET_SETTLEMENT"
    GROSS_SETTLEMENT = "GROSS_SETTLEMENT"


class OrderStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    PENDING = "PENDING"
    CANCELED = "CANCELED"
    EXCLUDED = "EXCLUDED"


class GroupType(StrEnum):
    ONE_TO_ONE = "ONE_TO_ONE"
    MANY_ORDERS_ONE_BANK = "MANY_ORDERS_ONE_BANK"
    ONE_ORDER_MANY_BANKS = "ONE_ORDER_MANY_BANKS"
    AMBIGUOUS_CANDIDATES = "AMBIGUOUS_CANDIDATES"


class LinkStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    PROPOSED = "PROPOSED"
    UNMATCHED = "UNMATCHED"
    REJECTED = "REJECTED"


class PaymentStatus(StrEnum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    OVERPAID = "OVERPAID"
    NO_CONFIRMED_RECEIPT = "NO_CONFIRMED_RECEIPT"
    UNKNOWN = "UNKNOWN"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"


class ReviewStatus(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    OPEN = "OPEN"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_MORE_INFO = "NEEDS_MORE_INFO"
    UNDONE = "UNDONE"


class Severity(StrEnum):
    BLOCKING = "BLOCKING"
    WARNING = "WARNING"
    INFO = "INFO"
