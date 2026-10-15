import { describe, expect, test } from "vitest";
import type { DashboardData } from "../types";
import {
  buildLayerChartModel,
  buildPaymentStatusChartModel,
  LAYER_PRESENTATION,
  PAYMENT_STATUS_PRESENTATION,
} from "./dashboardCharts";

function dashboard(paymentStatusCounts: Record<string, number>, eligibleOrders: number): DashboardData {
  return {
    run_id: "run-chart-test",
    effective_revision: 0,
    kpis: { eligible_orders_count: eligibleOrders },
    layer_counts: {},
    payment_status_counts: paymentStatusCounts,
    conservation: { is_valid: true, violations: [] },
  };
}

describe("biểu đồ nhóm đối chiếu", () => {
  test("giữ cố định bốn lớp đúng policy và hỗ trợ empty state", () => {
    const model = buildLayerChartModel({});
    expect(model.isEmpty).toBe(true);
    expect(model.rows.map((row) => row.code)).toEqual(["L1", "L2", "L3", "L4"]);
    expect(model.rows.map((row) => row.label)).toEqual(LAYER_PRESENTATION.map((row) => row.label));
  });

  test.each([
    [{ L1: { confirmed_groups: 1, proposed_groups: 0 } }, 1, 0],
    [{ L2: { confirmed_groups: 57, proposed_groups: 0 } }, 57, 0],
    [{ L3: { confirmed_groups: 0, proposed_groups: 4 } }, 0, 4],
    [{ L4: { confirmed_groups: 3, proposed_groups: 8 } }, 3, 8],
  ])("bảo toàn số nhóm confirmed và proposed %#", (counts, confirmed, proposed) => {
    const model = buildLayerChartModel(counts);
    expect(model.confirmedTotal).toBe(confirmed);
    expect(model.proposedTotal).toBe(proposed);
    expect(model.isEmpty).toBe(false);
  });

  test("không để dữ liệu không hữu hạn tạo NaN hoặc Infinity", () => {
    const model = buildLayerChartModel({
      L1: { confirmed_groups: Number.NaN, proposed_groups: Number.POSITIVE_INFINITY },
    });
    expect(model.confirmedTotal).toBe(0);
    expect(model.proposedTotal).toBe(0);
  });
});

describe("biểu đồ tình trạng thanh toán", () => {
  test("hiển thị đủ năm trạng thái với đúng mẫu số và phần trăm", () => {
    const model = buildPaymentStatusChartModel(dashboard({
      FULL: 87,
      PARTIAL: 2,
      OVERPAID: 1,
      NO_CONFIRMED_RECEIPT: 3,
      UNKNOWN: 7,
      NOT_ELIGIBLE: 4,
    }, 100));

    expect(model.rows).toHaveLength(5);
    expect(model.countedTotal).toBe(100);
    expect(model.eligibleTotal).toBe(100);
    expect(model.notEligibleCount).toBe(4);
    expect(model.isConsistent).toBe(true);
    expect(model.rows[0].legendLabel).toBe("Đã xác nhận thanh toán đủ — 87 đơn (87%)");
    expect(model.rows.reduce((total, row) => total + row.percentage, 0)).toBeCloseTo(100);
  });

  test("màu gắn với status key và không thay đổi theo thứ tự response", () => {
    const first = buildPaymentStatusChartModel(dashboard({ UNKNOWN: 1, FULL: 9 }, 10));
    const second = buildPaymentStatusChartModel(dashboard({ FULL: 8, UNKNOWN: 2 }, 10));
    const expectedColors = Object.fromEntries(PAYMENT_STATUS_PRESENTATION.map((row) => [row.code, row.color]));

    for (const row of [...first.rows, ...second.rows]) {
      expect(row.color).toBe(expectedColors[row.code]);
    }
    expect(first.rows.find((row) => row.code === "FULL")?.percentage).toBe(90);
    expect(second.rows.find((row) => row.code === "FULL")?.percentage).toBe(80);
  });

  test("hỗ trợ alias cũ, số trạng thái thay đổi và chỉ giữ trạng thái có dữ liệu", () => {
    const model = buildPaymentStatusChartModel(dashboard({ FULLY_SETTLED: 1, UNPAID: 1 }, 2));
    expect(model.rows.map((row) => row.code)).toEqual(["FULL", "NO_CONFIRMED_RECEIPT"]);
    expect(model.rows.map((row) => row.percentage)).toEqual([50, 50]);
  });

  test("empty state và mismatch không tạo phần trăm không hữu hạn", () => {
    const empty = buildPaymentStatusChartModel(dashboard({ FULL: Number.NaN }, 0));
    expect(empty.isEmpty).toBe(true);
    expect(empty.rows).toEqual([]);

    const mismatch = buildPaymentStatusChartModel(dashboard({ FULL: 1 }, 2));
    expect(mismatch.isConsistent).toBe(false);
    expect(mismatch.rows[0].percentage).toBe(50);
    expect(Number.isFinite(mismatch.rows[0].percentage)).toBe(true);
  });
});
