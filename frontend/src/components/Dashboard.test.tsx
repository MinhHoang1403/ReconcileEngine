import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

vi.mock("plotly.js/dist/plotly-basic.js", () => ({ default: {} }));
vi.mock("react-plotly.js/factory", () => ({ default: () => () => <div className="js-plotly-plot" /> }));
vi.mock("./ReconciliationReview", () => ({ ReconciliationReview: () => <div>Giao dịch cần xác minh</div> }));

import { Dashboard } from "./Dashboard";

const data = {
  run_id: "run-123",
  effective_revision: 1,
  kpis: {
    currency: "VND", expected_receivable_minor: 1000, confirmed_cash_allocated_minor: 800,
    verified_adjustments_minor: 0, outstanding_receivable_minor: 200, unapplied_bank_credit_minor: 50,
    fully_settled_orders_count: 1, unresolved_exceptions_count: 1,
  },
  layer_counts: { EXACT: { confirmed_groups: 1, proposed_groups: 1 } },
  payment_status_counts: { FULLY_SETTLED: 1, UNPAID: 1 },
  analytics: {
    review_status_counts: { OPEN: 1, APPROVED: 0, REJECTED: 0, UNDONE: 0 },
    review_decision_counts: { APPROVE_GROUP: 0, REJECT_GROUP: 0, UNDO_ACTION: 0 },
    method_summary: { confirmed_groups: 1, proposed_groups: 1, total_relation_groups: 2, confirmation_rate_percent: 50, confirmation_rate_denominator: "ALL_RELATION_GROUPS" },
    confirmed_group_type_counts: { ONE_TO_ONE: 1, MANY_ORDERS_ONE_BANK: 0, ONE_ORDER_MANY_BANKS: 0 },
    exception_reason_counts: { NO_CONFIRMED_RECEIPT: 1 },
    residual_distribution: {
      denominator_minor: 1000,
      order_outstanding: [{ bucket: "OVER_FIVE_PERCENT", count: 1, amount_minor: 200 }],
      bank_unapplied: [{ bucket: "OVER_FIVE_PERCENT", count: 1, amount_minor: 50 }],
    },
    confirmed_lag: { observation_unit: "ALLOCATION_PAIR", observations: 1, median_days: 0, buckets: [{ bucket: "SAME_DAY", count: 1 }] },
  },
  conservation: { is_valid: true, violations: [] },
};

test("dashboard sắp xếp đúng luồng, tra cứu trang hiện tại và xuất Excel", () => {
  render(<Dashboard
    data={data}
    runId="run-123"
    orders={[
      { order_id: "ORDER-001", expected_amount_minor: 800, allocated_cash_minor: 800, outstanding_minor: 0, payment_status: "FULLY_SETTLED" },
      { order_id: "ORDER-002", expected_amount_minor: 200, allocated_cash_minor: 0, outstanding_minor: 200, payment_status: "UNPAID" },
    ]}
    bankTransactions={[{ bank_txn_id: "BANK-001", posted_amount_minor: 850, allocated_cash_minor: 800, unapplied_minor: 50, direction: "CREDIT" }]}
    groups={[{ group_id: "group-1", group_type: "ONE_TO_ONE", order_ids: ["ORDER-001"], bank_txn_ids: ["BANK-001"], link_status: "PROPOSED", payment_statuses: {}, evidence: { rule_id: "R1", explanation_vi: "Cần kiểm tra", reason_codes: [] } }]}
    exceptions={[{ exception_id: "exception-1", reason_codes: ["UNMATCHED"], order_ids: ["ORDER-002"], bank_txn_ids: [], risk_amount_minor: 200 }]}
    totals={{ orders: 2, bank: 1, groups: 1, exceptions: 1 }}
    loadingMore={false}
    onLoadMore={vi.fn()}
    onRevisionChanged={vi.fn()}
  />);

  expect(screen.getByRole("heading", { name: "Tổng quan kiểm soát" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Phân tích kết quả" })).toBeInTheDocument();
  expect(screen.getByText(/1.000.*800.*0.*200/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Tải báo cáo Excel" })).toHaveAttribute("href", "/api/runs/run-123/exports?format=xlsx&expected_revision=1");
  expect(screen.getByText("50%")).toBeInTheDocument();
  fireEvent.change(screen.getByPlaceholderText("Tìm theo mã, trạng thái hoặc quy tắc…"), { target: { value: "ORDER-002" } });
  expect(screen.queryByText("ORDER-001")).not.toBeInTheDocument();
  expect(screen.getByText("ORDER-002")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: /Nhóm đối chiếu/ }));
  expect(screen.getByText("Đề xuất, chưa xác nhận", { selector: "span" })).toBeInTheDocument();
  expect(screen.getAllByText("run-123").length).toBeGreaterThan(0);
});
