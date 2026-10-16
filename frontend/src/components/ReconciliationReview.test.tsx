import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import type { ReviewHistoryItem, ReviewQueueItem } from "../types";

const mocks = vi.hoisted(() => ({
  reviews: vi.fn(),
  reviewHistory: vi.fn(),
  approveReview: vi.fn(),
  rejectReview: vi.fn(),
  undoReview: vi.fn(),
}));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, api: { ...actual.api, ...mocks } };
});

import { ReconciliationReview } from "./ReconciliationReview";

const proposal: ReviewQueueItem = {
  group_id: "CAND-1",
  group_type: "ONE_TO_ONE",
  order_ids: ["ORDER-1"],
  bank_txn_ids: ["BANK-1"],
  link_status: "PROPOSED",
  review_status: "OPEN",
  payment_statuses: { "ORDER-1": "UNKNOWN" },
  evidence: { rule_id: "L3_FUZZY", explanation_vi: "Tham chiếu gần giống", reason_codes: ["FUZZY_REFERENCE"] },
  order_records: [{ order_id: "ORDER-1", ordered_at: "2026-01-01", expected_amount_minor: 100_000, external_ref: "ORDER-1" }],
  bank_records: [{ bank_txn_id: "BANK-1", txn_date: "2026-01-01", posted_amount_minor: 100_000, direction: "CREDIT", amount_basis: "POSTED_CASH", txn_ref: "BANK-1" }],
  proposed_allocations: [{ edge_id: "EDGE-1", group_id: "CAND-1", order_id: "ORDER-1", bank_txn_id: "BANK-1", allocated_cash_minor: 100_000, currency: "VND" }],
  proposed_cash_minor: 100_000,
  competing_candidate_ids: [],
  can_approve: true,
  conflict_code: null,
  conflict_message: null,
};

const action = (type: "APPROVE_GROUP" | "REJECT_GROUP"): ReviewHistoryItem => ({
  action_id: "action-1",
  action_type: type,
  revision_before: 0,
  revision_after: 1,
  target_group_id: "CAND-1",
  actor_label: "ca-sang",
  actor_is_authenticated: false,
  note: "Đã kiểm tra",
  undo_of_action_id: null,
  allocation_delta_minor: type === "APPROVE_GROUP" ? 100_000 : 0,
  evidence: {},
  created_at: "2026-01-01T00:00:00Z",
});

beforeEach(() => {
  vi.clearAllMocks();
  mocks.reviews.mockResolvedValue({ run_id: "run-1", effective_revision: 0, items: [proposal], page: 1, page_size: 20, total: 1 });
  mocks.reviewHistory.mockResolvedValue({ run_id: "run-1", effective_revision: 0, items: [], page: 1, page_size: 20, total: 0 });
});

test("chấp thuận proposal, hiển thị allocation preview và refresh revision", async () => {
  const onRevisionChanged = vi.fn().mockResolvedValue(undefined);
  mocks.approveReview.mockResolvedValue({ action_type: "APPROVE_GROUP", effective_revision: 1 });
  mocks.reviews.mockResolvedValueOnce({ run_id: "run-1", effective_revision: 0, items: [proposal], page: 1, page_size: 20, total: 1 })
    .mockResolvedValue({ run_id: "run-1", effective_revision: 1, items: [], page: 1, page_size: 20, total: 0 });
  mocks.reviewHistory.mockResolvedValueOnce({ run_id: "run-1", effective_revision: 0, items: [], page: 1, page_size: 20, total: 0 })
    .mockResolvedValue({ run_id: "run-1", effective_revision: 1, items: [action("APPROVE_GROUP")], page: 1, page_size: 20, total: 1 });

  render(<ReconciliationReview runId="run-1" currency="VND" effectiveRevision={0} onOpenGroup={vi.fn()} onRevisionChanged={onRevisionChanged} />);
  fireEvent.click(await screen.findByRole("button", { name: "Xem và xử lý" }));
  expect(screen.getByText(/ORDER-1 ← BANK-1/)).toHaveTextContent("100.000");
  fireEvent.change(screen.getByPlaceholderText("Bằng chứng đã kiểm tra hoặc lý do từ chối"), { target: { value: "Đã đối chiếu chứng từ" } });
  fireEvent.click(screen.getByRole("button", { name: "Chấp thuận phân bổ" }));

  await waitFor(() => expect(mocks.approveReview).toHaveBeenCalledTimes(1));
  expect(mocks.approveReview.mock.calls[0][1]).toMatchObject({ group_id: "CAND-1", expected_revision: 0, note: "Đã đối chiếu chứng từ" });
  await waitFor(() => expect(onRevisionChanged).toHaveBeenCalledTimes(1));
  expect(await screen.findByRole("status")).toHaveTextContent("Revision hiệu lực: 1");
});

test("từ chối yêu cầu ghi chú và gửi quyết định không tạo allocation", async () => {
  mocks.rejectReview.mockResolvedValue({ action_type: "REJECT_GROUP", effective_revision: 1 });
  render(<ReconciliationReview runId="run-1" currency="VND" effectiveRevision={0} onOpenGroup={vi.fn()} onRevisionChanged={vi.fn()} />);

  fireEvent.click(await screen.findByRole("button", { name: "Xem và xử lý" }));
  expect(screen.getByRole("button", { name: "Từ chối đề xuất" })).toBeDisabled();
  fireEvent.change(screen.getByPlaceholderText("Bằng chứng đã kiểm tra hoặc lý do từ chối"), { target: { value: "Sai tham chiếu" } });
  fireEvent.click(screen.getByRole("button", { name: "Từ chối đề xuất" }));

  await waitFor(() => expect(mocks.rejectReview).toHaveBeenCalledTimes(1));
  expect(mocks.rejectReview.mock.calls[0][1]).toMatchObject({ group_id: "CAND-1", note: "Sai tham chiếu" });
});
