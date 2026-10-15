import { describe, expect, test } from "vitest";
import { asSafeMinorUnit, formatMoney } from "./money";

describe("hiển thị integer minor units", () => {
  test("giữ chính xác VND và BRL trong giới hạn số nguyên an toàn", () => {
    expect(asSafeMinorUnit("9007199254740991")).toBe(Number.MAX_SAFE_INTEGER);
    expect(formatMoney(1234, "VND")).toContain("1.234");
    expect(formatMoney(1234, "BRL")).toContain("12,34");
  });

  test("không biến dữ liệu thiếu hoặc không an toàn thành 0", () => {
    expect(formatMoney(undefined, "VND")).toBe("Không có dữ liệu");
    expect(formatMoney(Number.NaN, "VND")).toBe("Giá trị vượt giới hạn hiển thị an toàn");
    expect(formatMoney("9007199254740992", "VND")).toBe("Giá trị vượt giới hạn hiển thị an toàn");
  });
});
