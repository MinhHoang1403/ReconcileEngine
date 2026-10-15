import { useMemo, useState } from "react";
import Plotly from "plotly.js/dist/plotly-basic.js";
import createPlotlyComponent from "react-plotly.js/factory";
import type { BankRow, DashboardData, ExceptionRow, GroupRow, OrderRow } from "../types";

const Plot = createPlotlyComponent(Plotly);
type ExplorerTab = "orders" | "bank" | "groups" | "exceptions";

const paymentStatus: Record<string, string> = {
  FULL: "Đã thu đủ",
  PARTIAL: "Thu một phần",
  NO_CONFIRMED_RECEIPT: "Chưa có tiền xác nhận",
  UNKNOWN: "Chưa xác định",
  NOT_ELIGIBLE: "Không đủ điều kiện",
  FULLY_SETTLED: "Đã thu đủ",
  PARTIALLY_SETTLED: "Thu một phần",
  UNPAID: "Chưa thu",
  OVERPAID: "Thu thừa",
};
const linkStatus: Record<string, string> = { CONFIRMED: "Đã xác nhận", PROPOSED: "Đề xuất" };

function formatMoney(value: unknown, currency: string): string {
  const numeric = typeof value === "number" ? value : Number(value ?? 0);
  const divisor = currency === "BRL" ? 100 : 1;
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "BRL" ? 2 : 0,
  }).format(numeric / divisor);
}

function includesQuery(values: unknown[], query: string) {
  if (!query) return true;
  return values.some((value) => String(value ?? "").toLocaleLowerCase("vi").includes(query));
}

export function Dashboard({ data, groups, exceptions, orders, bankTransactions, runId }: {
  data: DashboardData;
  groups: GroupRow[];
  exceptions: ExceptionRow[];
  orders: OrderRow[];
  bankTransactions: BankRow[];
  runId: string;
}) {
  const [tab, setTab] = useState<ExplorerTab>("orders");
  const [query, setQuery] = useState("");
  const [groupStatus, setGroupStatus] = useState("ALL");
  const currency = String(data.kpis.currency ?? "VND");
  const normalizedQuery = query.trim().toLocaleLowerCase("vi");
  const layers = Object.keys(data.layer_counts);
  const paymentLabels = Object.keys(data.payment_status_counts).filter((key) => data.payment_status_counts[key] > 0);
  const moneyCards = [
    ["Tổng phải thu", "expected_receivable_minor"],
    ["Tiền đã phân bổ", "confirmed_cash_allocated_minor"],
    ["Phải thu còn lại", "outstanding_receivable_minor"],
    ["Tiền ngân hàng chưa phân bổ", "unapplied_bank_credit_minor"],
  ] as const;

  const filteredOrders = useMemo(
    () => orders.filter((row) => includesQuery([row.order_id, row.payment_status], normalizedQuery)),
    [orders, normalizedQuery],
  );
  const filteredBank = useMemo(
    () => bankTransactions.filter((row) => includesQuery([row.bank_txn_id, row.direction], normalizedQuery)),
    [bankTransactions, normalizedQuery],
  );
  const filteredGroups = useMemo(
    () => groups.filter((row) =>
      (groupStatus === "ALL" || row.link_status === groupStatus)
      && includesQuery([row.group_id, row.group_type, row.order_ids.join(" "), row.bank_txn_ids.join(" "), row.evidence.rule_id], normalizedQuery),
    ),
    [groups, groupStatus, normalizedQuery],
  );
  const filteredExceptions = useMemo(
    () => exceptions.filter((row) => includesQuery([row.exception_id, row.reason_codes.join(" "), row.order_ids.join(" "), row.bank_txn_ids.join(" ")], normalizedQuery)),
    [exceptions, normalizedQuery],
  );

  const tabs: { id: ExplorerTab; label: string; count: number }[] = [
    { id: "orders", label: "Khoản phải thu", count: orders.length },
    { id: "bank", label: "Ngân hàng / PSP", count: bankTransactions.length },
    { id: "groups", label: "Nhóm đối soát", count: groups.length },
    { id: "exceptions", label: "Ngoại lệ", count: exceptions.length },
  ];
  const visibleCount = { orders: filteredOrders.length, bank: filteredBank.length, groups: filteredGroups.length, exceptions: filteredExceptions.length }[tab];
  const loadedCount = { orders: orders.length, bank: bankTransactions.length, groups: groups.length, exceptions: exceptions.length }[tab];

  function selectTab(next: ExplorerTab) {
    setTab(next);
    setQuery("");
  }

  return (
    <div className="dashboard-stack">
      <section className="dashboard-section" aria-labelledby="overview-title">
        <div className="section-label"><span>A</span><div><h2 id="overview-title">Tổng quan kiểm soát</h2><p>Các KPI chỉ phản ánh phân bổ đã xác nhận.</p></div></div>
        <div className="kpi-grid">
          {moneyCards.map(([label, key]) => (
            <article className="kpi-card" key={key}><span>{label}</span><strong>{formatMoney(data.kpis[key], currency)}</strong></article>
          ))}
          <article className="kpi-card"><span>Khoản thu đã đủ tiền</span><strong>{String(data.kpis.fully_settled_orders_count)}</strong></article>
          <article className="kpi-card attention"><span>Ngoại lệ chưa xử lý</span><strong>{String(data.kpis.unresolved_exceptions_count)}</strong></article>
        </div>
      </section>

      <section className="dashboard-section" aria-labelledby="analysis-title">
        <div className="section-label"><span>B</span><div><h2 id="analysis-title">Phân tích kết quả</h2><p>Quan sát waterfall và trạng thái thu tiền.</p></div></div>
        <div className="chart-grid">
          <article className="surface chart-card">
            <div className="chart-heading"><div><h3>Waterfall theo lớp</h3><p>Đề xuất được tách riêng, không cộng vào KPI đã xác nhận.</p></div><span className="proposal-note">■ Đề xuất</span></div>
            <Plot
              data={[
                { type: "bar", name: "Đã xác nhận", x: layers, y: layers.map((layer) => data.layer_counts[layer].confirmed_groups), marker: { color: "#176b4d" } },
                { type: "bar", name: "Đề xuất", x: layers, y: layers.map((layer) => data.layer_counts[layer].proposed_groups), marker: { color: "#d49320" } },
              ]}
              layout={{ barmode: "stack", margin: { l: 42, r: 14, t: 18, b: 48 }, paper_bgcolor: "transparent", plot_bgcolor: "transparent", autosize: true, legend: { orientation: "h" }, font: { family: "Segoe UI, Arial, sans-serif", color: "#44534c" } }}
              config={{ displayModeBar: false, responsive: true }} useResizeHandler style={{ width: "100%", height: 300 }}
            />
          </article>
          <article className="surface chart-card">
            <div className="chart-heading"><div><h3>Trạng thái khoản phải thu</h3><p>Phân bố trạng thái trên toàn phiên đối soát.</p></div></div>
            <Plot
              data={[{ type: "pie", hole: 0.62, labels: paymentLabels.map((label) => paymentStatus[label] ?? label), values: paymentLabels.map((label) => data.payment_status_counts[label]), marker: { colors: ["#176b4d", "#d49320", "#b9493f", "#7b8b83"] } }]}
              layout={{ margin: { l: 10, r: 10, t: 18, b: 20 }, paper_bgcolor: "transparent", autosize: true, showlegend: true, font: { family: "Segoe UI, Arial, sans-serif", color: "#44534c" } }}
              config={{ displayModeBar: false, responsive: true }} useResizeHandler style={{ width: "100%", height: 300 }}
            />
          </article>
        </div>
      </section>

      <section className="dashboard-section" aria-labelledby="explorer-title">
        <div className="section-label"><span>C</span><div><h2 id="explorer-title">Tra cứu chi tiết</h2><p>Tìm kiếm trong các bản ghi đã tải từ trang API hiện tại.</p></div></div>
        <article className="surface explorer-card">
          <div className="explorer-tabs" role="tablist" aria-label="Loại dữ liệu tra cứu">
            {tabs.map((item) => (
              <button key={item.id} type="button" role="tab" aria-selected={tab === item.id} className={tab === item.id ? "active" : ""} onClick={() => selectTab(item.id)}>
                {item.label}<span>{item.count}</span>
              </button>
            ))}
          </div>
          <div className="explorer-tools">
            <label className="search-field"><span className="sr-only">Tìm kiếm trong bảng</span><span aria-hidden="true">⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm theo mã, trạng thái hoặc quy tắc…" /></label>
            {tab === "groups" && (
              <label className="filter-field"><span className="sr-only">Lọc trạng thái nhóm</span><select value={groupStatus} onChange={(event) => setGroupStatus(event.target.value)}><option value="ALL">Tất cả trạng thái</option><option value="CONFIRMED">Đã xác nhận</option><option value="PROPOSED">Đề xuất</option></select></label>
            )}
            <span className="loaded-count">{visibleCount} / {loadedCount} bản ghi đã tải</span>
          </div>
          <div className="table-wrap explorer-table">
            {tab === "orders" && <table><caption className="sr-only">Khoản phải thu</caption><thead><tr><th>Mã khoản thu</th><th>Phải thu</th><th>Đã phân bổ</th><th>Còn lại</th><th>Trạng thái</th></tr></thead><tbody>{filteredOrders.map((row) => <tr key={row.order_id}><td className="id-cell">{row.order_id}</td><td>{formatMoney(row.expected_amount_minor, currency)}</td><td>{formatMoney(row.allocated_cash_minor, currency)}</td><td>{formatMoney(row.outstanding_minor, currency)}</td><td><span className={`status-tag status-${row.payment_status.toLowerCase()}`} title={row.payment_status}>{paymentStatus[row.payment_status] ?? row.payment_status}</span></td></tr>)}</tbody></table>}
            {tab === "bank" && <table><caption className="sr-only">Giao dịch ngân hàng và PSP</caption><thead><tr><th>Mã giao dịch</th><th>Số tiền</th><th>Đã phân bổ</th><th>Chưa phân bổ</th><th>Chiều</th></tr></thead><tbody>{filteredBank.map((row) => <tr key={row.bank_txn_id}><td className="id-cell">{row.bank_txn_id}</td><td>{formatMoney(row.posted_amount_minor, currency)}</td><td>{formatMoney(row.allocated_cash_minor, currency)}</td><td>{formatMoney(row.unapplied_minor, currency)}</td><td>{row.direction === "CREDIT" ? "Ghi có" : row.direction === "DEBIT" ? "Ghi nợ" : row.direction}</td></tr>)}</tbody></table>}
            {tab === "groups" && <table><caption className="sr-only">Nhóm đối soát</caption><thead><tr><th>Loại</th><th>Khoản thu</th><th>Giao dịch ngân hàng</th><th>Trạng thái</th><th>Quy tắc</th><th>Giải thích</th></tr></thead><tbody>{filteredGroups.map((group) => <tr key={group.group_id}><td>{group.group_type}</td><td>{group.order_ids.join(", ")}</td><td>{group.bank_txn_ids.join(", ")}</td><td><span className={`status-tag status-${group.link_status.toLowerCase()}`} title={group.link_status}>{linkStatus[group.link_status] ?? group.link_status}</span></td><td><code>{group.evidence.rule_id}</code></td><td>{group.evidence.explanation_vi}</td></tr>)}</tbody></table>}
            {tab === "exceptions" && <table><caption className="sr-only">Ngoại lệ và số dư</caption><thead><tr><th>Lý do kỹ thuật</th><th>Khoản thu</th><th>Giao dịch ngân hàng</th><th>Giá trị rủi ro</th></tr></thead><tbody>{filteredExceptions.map((item) => <tr key={item.exception_id}><td>{item.reason_codes.map((code) => <code key={code}>{code} </code>)}</td><td>{item.order_ids.join(", ") || "—"}</td><td>{item.bank_txn_ids.join(", ") || "—"}</td><td>{formatMoney(item.risk_amount_minor, currency)}</td></tr>)}</tbody></table>}
          </div>
          {visibleCount === 0 && <p className="empty-state">Không tìm thấy bản ghi phù hợp.</p>}
        </article>
      </section>

      <section className="dashboard-section" aria-labelledby="export-title">
        <div className="section-label"><span>D</span><div><h2 id="export-title">Xuất báo cáo và truy vết</h2><p>Lưu workbook đầy đủ để kiểm tra hoặc bàn giao.</p></div></div>
        <article className={`surface export-panel ${data.conservation.is_valid ? "valid" : "invalid"}`}>
          <div className="export-status"><span aria-hidden="true">{data.conservation.is_valid ? "✓" : "!"}</span><div><strong>{data.conservation.is_valid ? "Bảo toàn tiền đã được xác minh" : "Phát hiện vi phạm bảo toàn tiền"}</strong><p>{data.conservation.is_valid ? "Không có chênh lệch phân bổ ngoài quy tắc." : data.conservation.violations.join(", ")}</p></div></div>
          <dl><div><dt>Run ID</dt><dd>{runId}</dd></div><div><dt>Revision</dt><dd>{data.effective_revision}</dd></div><div><dt>Định dạng</dt><dd>Excel (.xlsx)</dd></div></dl>
          <a className="primary link-button" href={`/api/runs/${runId}/exports?format=xlsx`}>Tải báo cáo Excel</a>
        </article>
      </section>
    </div>
  );
}
