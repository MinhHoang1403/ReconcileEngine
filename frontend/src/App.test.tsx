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
