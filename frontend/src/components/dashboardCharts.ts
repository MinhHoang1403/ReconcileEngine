import type { DashboardData } from "../types";

type CountPair = { confirmed_groups: number; proposed_groups: number };

export const LAYER_PRESENTATION = [
  { code: "L1", label: "Ghép theo mã tham chiếu rõ ràng", tickLabel: "Ghép theo mã tham chiếu<br>rõ ràng" },
  { code: "L2", label: "Ghép theo mã và điều kiện nghiệp vụ", tickLabel: "Ghép theo mã và<br>điều kiện nghiệp vụ" },
  { code: "L3", label: "Đề xuất từ thông tin gần giống", tickLabel: "Đề xuất từ thông tin<br>gần giống" },
  { code: "L4", label: "Đề xuất thanh toán gộp hoặc chia lần", tickLabel: "Đề xuất thanh toán gộp<br>hoặc chia lần" },
] as const;

export const PAYMENT_STATUS_PRESENTATION = [
  { code: "FULL", label: "Đã xác nhận thanh toán đủ", color: "#176b4d" },
  { code: "PARTIAL", label: "Đã xác nhận thanh toán một phần", color: "#d49320" },
  { code: "OVERPAID", label: "Đã thu đủ, còn tiền nhận chưa phân bổ", color: "#276a82" },
  { code: "NO_CONFIRMED_RECEIPT", label: "Chưa có khoản tiền được xác nhận", color: "#b9493f" },
  { code: "UNKNOWN", label: "Chưa xác định", color: "#6d5c80" },
] as const;

const PAYMENT_STATUS_ALIASES: Record<string, string> = {
  FULLY_SETTLED: "FULL",
  PARTIALLY_SETTLED: "PARTIAL",
  UNPAID: "NO_CONFIRMED_RECEIPT",
};

function safeCount(value: unknown): number {
  const count = typeof value === "number" ? value : Number(value);
  return Number.isFinite(count) && count > 0 ? Math.floor(count) : 0;
}

export function buildLayerChartModel(layerCounts: Record<string, CountPair>) {
  const rows = LAYER_PRESENTATION.map((layer) => ({
    ...layer,
    confirmed: safeCount(layerCounts[layer.code]?.confirmed_groups),
    proposed: safeCount(layerCounts[layer.code]?.proposed_groups),
  }));
  return {
    rows,
    confirmedTotal: rows.reduce((total, row) => total + row.confirmed, 0),
    proposedTotal: rows.reduce((total, row) => total + row.proposed, 0),
    isEmpty: rows.every((row) => row.confirmed === 0 && row.proposed === 0),
  };
}

export function buildPaymentStatusChartModel(data: DashboardData) {
  const canonicalCounts: Record<string, number> = {};
  for (const [rawCode, rawCount] of Object.entries(data.payment_status_counts)) {
    const code = PAYMENT_STATUS_ALIASES[rawCode] ?? rawCode;
    canonicalCounts[code] = (canonicalCounts[code] ?? 0) + safeCount(rawCount);
  }

  const chartCount = PAYMENT_STATUS_PRESENTATION.reduce(
    (total, status) => total + (canonicalCounts[status.code] ?? 0),
    0,
  );
  const eligibleFromKpi = safeCount(data.kpis.eligible_orders_count);
  const eligibleTotal = eligibleFromKpi || chartCount;
  const notEligibleCount = canonicalCounts.NOT_ELIGIBLE ?? 0;
  const rows = PAYMENT_STATUS_PRESENTATION.map((status) => {
    const count = canonicalCounts[status.code] ?? 0;
    const percentage = eligibleTotal > 0 ? (count / eligibleTotal) * 100 : 0;
    return {
      ...status,
      count,
      percentage,
      legendLabel: `${status.label} — ${count.toLocaleString("vi-VN")} đơn (${percentage.toLocaleString("vi-VN", { maximumFractionDigits: 1 })}%)`,
    };
  }).filter((status) => status.count > 0);

  return {
    rows,
    eligibleTotal,
    notEligibleCount,
    countedTotal: chartCount,
    isConsistent: chartCount === eligibleTotal,
    isEmpty: eligibleTotal === 0,
  };
}
