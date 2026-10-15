import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { HealthGate } from "./HealthGate";

test("Health Gate khóa chạy và yêu cầu lý do loại trừ hợp lệ", () => {
  const onExclude = vi.fn();
  render(<HealthGate
    health={{
      session_id: "s1", status: "MAPPED", exclusions: [], acknowledged_issue_codes: [],
      report: { status: "BLOCKED", blocking_count: 1, warning_count: 0, info_count: 0, issues: [{ code: "INVALID_AMOUNT", severity: "BLOCKING", feed: "orders", message_vi: "Số tiền không hợp lệ", source_rows: [4], sample_values: ["abc"] }] },
      standardized_eda: { eligible_orders_count: 0, eligible_credit_count: 1 },
    }}
    busy={false} onAcknowledge={vi.fn()} onExclude={onExclude} onRun={vi.fn()} onBack={vi.fn()}
  />);
  expect(screen.getByRole("button", { name: "Chạy đối soát" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Loại trừ các dòng này" }));
  const confirm = screen.getByRole("button", { name: "Xác nhận loại trừ" });
  expect(confirm).toBeDisabled();
  fireEvent.change(screen.getByLabelText(/Lý do loại trừ/), { target: { value: "Sai dữ liệu nguồn" } });
  fireEvent.click(confirm);
  expect(onExclude).toHaveBeenCalledWith(expect.objectContaining({ code: "INVALID_AMOUNT" }), "Sai dữ liệu nguồn");
});
