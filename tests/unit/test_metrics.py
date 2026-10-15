from datetime import date

from smartrecon.analytics.metrics import calculate_kpis
from smartrecon.domain.models import Order
from smartrecon.domain.statuses import Currency


def test_zero_value_order_without_confirmed_evidence_is_not_fully_settled() -> None:
    order = Order(
        order_id="ZERO-1",
        ordered_at=date(2026, 1, 1),
        expected_amount_minor=0,
        currency=Currency.VND,
    )

    kpis = calculate_kpis([order], [], [], [], [], [])

    assert kpis["fully_settled_orders_count"] == 0
    assert kpis["no_confirmed_receipt_orders_count"] == 1
    assert kpis["payment_status_counts"]["NO_CONFIRMED_RECEIPT"] == 1
