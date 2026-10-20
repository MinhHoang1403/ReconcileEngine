import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

vi.mock("./components/Dashboard", () => ({ Dashboard: () => <div>Khu vực dashboard</div> }));

import { App } from "./App";

const inspection = {
  session_id: "session-1",
  status: "INSPECTED",
  dataset_profile: "demo",
  raw_eda: {
    orders: { row_count: 1, column_count: 3, columns: ["order_id", "ordered_at", "expected_amount"], missing_by_column: {}, duplicate_rows: 0, sample_rows: [{ order_id: "A1" }], confidence: "HIGH" },
    bank_transactions: { row_count: 1, column_count: 5, columns: ["bank_txn_id", "txn_date", "posted_amount", "direction", "amount_basis"], missing_by_column: {}, duplicate_rows: 0, sample_rows: [{ bank_txn_id: "B1" }], confidence: "HIGH" },
  },
  suggested_mapping: {
    order_columns: { order_id: "order_id", ordered_at: "ordered_at", expected_amount: "expected_amount" },
    bank_columns: { bank_txn_id: "bank_txn_id", txn_date: "txn_date", posted_amount: "posted_amount", direction: "direction", amount_basis: "amount_basis" },
  },
};

const safeMapping = {
  ...inspection.suggested_mapping, currency: "VND", source_profile: "BANK_CREDIT", date_format: "AUTO",
  decimal_separator: ".", thousand_separator: null, order_defaults: { order_status: "ELIGIBLE" }, bank_defaults: {},
  confirmed_structure: true, order_date_format: "AUTO", bank_date_format: "AUTO", order_transformations: {},
  bank_transformations: {}, transformation_version: "smart-import-2026-10-16", confirmed_ambiguities: [],
  import_profile_id: null, import_profile_schema_version: null,
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

test("hiển thị trạng thái sẵn sàng và khóa upload khi chưa đủ hai file", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ status: "ok", database: "ok" }), { status: 200 }));
  render(<App />);
  expect(await screen.findByText("Hệ thống sẵn sàng")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Kiểm tra và xem trước" })).toBeDisabled();
  expect(screen.getByRole("navigation", { name: "Tiến trình đối soát" })).toBeInTheDocument();
});

test("dữ liệu mẫu chuyển sang màn hình khám phá và ánh xạ", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    const body = url === "/healthz" ? { status: "ok", database: "ok" } : inspection;
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
  });
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "Sử dụng dữ liệu mẫu" }));
  expect(await screen.findByRole("heading", { name: "Kiểm tra và chuẩn hóa dữ liệu" })).toBeInTheDocument();
  expect(screen.getAllByText("Trường bắt buộc", { selector: "h3" })).toHaveLength(2);
});

test("hiển thị và cho phép đóng lỗi API", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    if (String(input) === "/healthz") return Promise.resolve(new Response(JSON.stringify({ status: "ok", database: "ok" }), { status: 200 }));
    return Promise.resolve(new Response(JSON.stringify({ detail: "Không tạo được dữ liệu mẫu" }), { status: 500 }));
  });
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "Sử dụng dữ liệu mẫu" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Không tạo được dữ liệu mẫu");
  fireEvent.click(screen.getByRole("button", { name: "Đóng thông báo lỗi" }));
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
});

test("không điền cột tiền bằng gợi ý cũ khi bộ phân tích yêu cầu xác nhận", async () => {
  const prepared = {
    ...inspection,
    raw_eda: { ...inspection.raw_eda, orders: { ...inspection.raw_eda.orders, columns: ["order_id", "ordered_at", "Amount Due", "Balance Due"] } },
    suggested_mapping: { ...inspection.suggested_mapping, order_columns: { order_id: "order_id", ordered_at: "ordered_at", expected_amount: "Amount Due" } },
    mapping_suggestions: {
      orders: {
        suggestions: [{ canonical_target: "expected_amount", source_column: "Amount Due", transformation: { type: "DIRECT" }, heuristic_score: 100, confidence: "HIGH", reasons: ["Hai cột tiền cùng nghĩa có điểm ngang nhau"], competitors: [{ source_column: "Balance Due", heuristic_score: 100, reasons: [] }], sample_before: [], sample_after: [], status: "needs-review" }],
        selected_mapping: { order_id: "order_id", ordered_at: "ordered_at" }, selected_transformations: {},
        required_total: 3, required_auto_selected: 2, required_needs_review: 1, required_unsupported: 0,
      },
      bank_transactions: { suggestions: [], selected_mapping: inspection.suggested_mapping.bank_columns, selected_transformations: {}, required_total: 5, required_auto_selected: 5, required_needs_review: 0, required_unsupported: 0 },
    },
  };
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => Promise.resolve(new Response(JSON.stringify(String(input) === "/healthz" ? { status: "ok", database: "ok" } : prepared), { status: 200 })));
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "Sử dụng dữ liệu mẫu" }));
  await screen.findByRole("heading", { name: "Kiểm tra và chuẩn hóa dữ liệu" });
  const amount = screen.getByRole("combobox", { name: /Số tiền cần thu/ });
  expect(amount).toHaveValue("");
  expect(screen.getByRole("button", { name: "Xác nhận và chuẩn hóa dữ liệu" })).toBeDisabled();
});

test("nguồn rõ ràng tự kiểm tra chất lượng nhưng không tự chạy đối soát", async () => {
  const health = { session_id: "session-1", status: "HEALTH_READY", report: { status: "READY", blocking_count: 0, warning_count: 0, info_count: 0, issues: [] }, standardized_eda: {}, exclusions: [], acknowledged_issue_codes: [] };
  const requests: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    requests.push(url);
    const body = url === "/healthz" ? { status: "ok", database: "ok" } : url.endsWith("/mapping") ? health : { ...inspection, automatic_mapping: safeMapping, automation_reasons: [] };
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
  });
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "Sử dụng dữ liệu mẫu" }));
  expect(await screen.findByRole("heading", { name: "Dữ liệu sẵn sàng đối soát" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Chạy đối soát" })).toBeEnabled();
  expect(requests.filter((url) => url.endsWith("/mapping"))).toHaveLength(1);
  expect(requests).not.toContain("/api/runs");
});

test("lỗi kiểm tra tự động trả về chỉnh dữ liệu và không tạo phiên đối soát", async () => {
  const requests: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    requests.push(url);
    if (url.endsWith("/mapping")) return Promise.resolve(new Response(JSON.stringify({ detail: "Không đọc được dữ liệu nguồn" }), { status: 500 }));
    return Promise.resolve(new Response(JSON.stringify(url === "/healthz" ? { status: "ok", database: "ok" } : { ...inspection, automatic_mapping: safeMapping }), { status: 200 }));
  });
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "Sử dụng dữ liệu mẫu" }));
  expect(await screen.findByRole("heading", { name: "Kiểm tra và chuẩn hóa dữ liệu" })).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("Không đọc được dữ liệu nguồn");
  expect(requests).not.toContain("/api/runs");
});

test("câu hỏi dấu phân cách mở cấu hình và giữ lựa chọn khi xác nhận", async () => {
  let submitted: Record<string, unknown> | undefined;
  const analyses = (selected: Record<string, string>) => ({
    suggestions: Object.entries(selected).map(([canonical_target, source_column]) => ({ canonical_target, source_column, transformation: { type: "DIRECT" }, heuristic_score: 100, confidence: "HIGH", reasons: [], competitors: [], sample_before: [], sample_after: [], status: "auto-selected" })),
    selected_mapping: selected, selected_transformations: {}, required_total: Object.keys(selected).length, required_auto_selected: Object.keys(selected).length, required_needs_review: 0, required_unsupported: 0,
  });
  const prepared = { ...inspection, automatic_mapping: null, automation_reasons: ["MONEY_FORMAT_REQUIRES_CONFIRMATION"], mapping_suggestions: { orders: analyses(safeMapping.order_columns), bank_transactions: analyses(safeMapping.bank_columns) } };
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    if (url.endsWith("/mapping")) submitted = JSON.parse(String(init?.body));
    const body = url === "/healthz" ? { status: "ok", database: "ok" } : url.endsWith("/mapping") ? { session_id: "session-1", report: { status: "READY", issues: [], blocking_count: 0, warning_count: 0, info_count: 0 }, standardized_eda: {}, exclusions: [], acknowledged_issue_codes: [] } : prepared;
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
  });
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "Sử dụng dữ liệu mẫu" }));
  await screen.findByRole("heading", { name: "Kiểm tra và chuẩn hóa dữ liệu" });
  expect(screen.getByText(/Ví dụ 1.000 có thể được hiểu khác nhau/)).toBeInTheDocument();
  expect(screen.getByText("Cách đọc tiền, ngày và loại tiền").closest("details")).toHaveAttribute("open");
  fireEvent.change(screen.getByRole("combobox", { name: "Dấu thập phân" }), { target: { value: "," } });
  expect(screen.getByRole("combobox", { name: "Dấu phân cách hàng nghìn" })).toHaveValue("");
  fireEvent.change(screen.getByRole("combobox", { name: "Dấu phân cách hàng nghìn" }), { target: { value: "." } });
  fireEvent.click(screen.getByRole("button", { name: "Xác nhận và chuẩn hóa dữ liệu" }));
  await screen.findByRole("heading", { name: "Dữ liệu sẵn sàng đối soát" });
  expect(submitted?.decimal_separator).toBe(",");
  expect(submitted?.thousand_separator).toBe(".");
});
