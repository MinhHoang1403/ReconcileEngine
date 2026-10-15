import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";

afterEach(() => {
  vi.restoreAllMocks();
});

test("hiển thị trạng thái sẵn sàng từ API", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ status: "ok", database: "ok" }), { status: 200 }),
  );
  render(<App />);
  expect(await screen.findByText("Backend và PostgreSQL đã sẵn sàng")).toBeInTheDocument();
});

