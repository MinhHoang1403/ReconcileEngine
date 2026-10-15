export function asSafeMinorUnit(value: unknown): number | null {
  if (typeof value === "number") {
    return Number.isSafeInteger(value) ? value : null;
  }
  if (typeof value === "string" && /^-?\d+$/.test(value.trim())) {
    const parsed = BigInt(value.trim());
    if (parsed >= BigInt(Number.MIN_SAFE_INTEGER) && parsed <= BigInt(Number.MAX_SAFE_INTEGER)) {
      return Number(parsed);
    }
  }
  return null;
}

export function formatMoney(value: unknown, currency: string): string {
  const minorUnits = asSafeMinorUnit(value);
  if (minorUnits === null) {
    return value === null || value === undefined || value === ""
      ? "Không có dữ liệu"
      : "Giá trị vượt giới hạn hiển thị an toàn";
  }
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "BRL" ? 2 : 0,
  }).format(minorUnits / (currency === "BRL" ? 100 : 1));
}
