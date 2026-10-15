import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

vi.mock("./components/Dashboard", () => ({ Dashboard: () => null }));

import { App } from "./App";

afterEach(() => {
  vi.restoreAllMocks();
});

test("hiển thị trạng thái sẵn sàng từ API", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ status: "ok", database: "ok" }), { status: 200 }),
  );
  render(<App />);
  expect(await screen.findByText("Hệ thống sẵn sàng")).toBeInTheDocument();
});
