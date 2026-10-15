import Plotly from "plotly.js/dist/plotly-basic.js";
import createPlotlyComponent from "react-plotly.js/factory";
import type { BankRow, DashboardData, ExceptionRow, GroupRow, OrderRow } from "../types";

const Plot = createPlotlyComponent(Plotly);

function formatMoney(value: unknown, currency: string): string {
  const numeric = typeof value === "number" ? value : Number(value ?? 0);
  const divisor = currency === "BRL" ? 100 : 1;
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "BRL" ? 2 : 0,
  }).format(numeric / divisor);
}

export function Dashboard({
  data,
  groups,
  exceptions,
  orders,
  bankTransactions,
}: {
  data: DashboardData;
  groups: GroupRow[];
  exceptions: ExceptionRow[];
  orders: OrderRow[];
  bankTransactions: BankRow[];
}) {
  const currency = String(data.kpis.currency ?? "VND");
  const moneyCards = [
    ["Tổng phải thu", "expected_receivable_minor"],
    ["Cash đã phân bổ", "confirmed_cash_allocated_minor"],
    ["Phải thu còn lại", "outstanding_receivable_minor"],
    ["Bank chưa phân bổ", "unapplied_bank_credit_minor"],
  ];
  const layers = Object.keys(data.layer_counts);
  const paymentLabels = Object.keys(data.payment_status_counts).filter(
    (key) => data.payment_status_counts[key] > 0,
  );
  return (
    <div className="stack">
      <div className="kpi-grid">
        {moneyCards.map(([label, key]) => (
          <article className="kpi-card" key={key}>
            <span>{label}</span>
            <strong>{formatMoney(data.kpis[key], currency)}</strong>
          </article>
        ))}
        <article className="kpi-card"><span>Đơn đã đủ tiền</span><strong>{String(data.kpis.fully_settled_orders_count)}</strong></article>
        <article className="kpi-card"><span>Exceptions</span><strong>{String(data.kpis.unresolved_exceptions_count)}</strong></article>
      </div>
      <div className="two-column">
        <article className="data-card">
          <div className="data-card__header"><h3>Khoản phải thu</h3><span className="count-pill">{orders.length}</span></div>
          <div className="table-wrap compact-table"><table><thead><tr><th>Order</th><th>Expected</th><th>Allocated</th><th>Residual</th><th>Status</th></tr></thead><tbody>{orders.slice(0, 30).map((row) => <tr key={row.order_id}><td>{row.order_id}</td><td>{formatMoney(row.expected_amount_minor, currency)}</td><td>{formatMoney(row.allocated_cash_minor, currency)}</td><td>{formatMoney(row.outstanding_minor, currency)}</td><td>{row.payment_status}</td></tr>)}</tbody></table></div>
        </article>
        <article className="data-card">
          <div className="data-card__header"><h3>Giao dịch ngân hàng</h3><span className="count-pill">{bankTransactions.length}</span></div>
          <div className="table-wrap compact-table"><table><thead><tr><th>Bank ID</th><th>Amount</th><th>Allocated</th><th>Unapplied</th><th>Direction</th></tr></thead><tbody>{bankTransactions.slice(0, 30).map((row) => <tr key={row.bank_txn_id}><td>{row.bank_txn_id}</td><td>{formatMoney(row.posted_amount_minor, currency)}</td><td>{formatMoney(row.allocated_cash_minor, currency)}</td><td>{formatMoney(row.unapplied_minor, currency)}</td><td>{row.direction}</td></tr>)}</tbody></table></div>
        </article>
      </div>
      <div className="two-column charts">
        <article className="data-card">
          <h3>Waterfall theo lớp</h3>
          <Plot
            data={[
              { type: "bar", name: "Confirmed", x: layers, y: layers.map((layer) => data.layer_counts[layer].confirmed_groups), marker: { color: "#28795b" } },
              { type: "bar", name: "Proposed", x: layers, y: layers.map((layer) => data.layer_counts[layer].proposed_groups), marker: { color: "#d5a134" } },
            ]}
            layout={{ barmode: "stack", margin: { l: 36, r: 10, t: 20, b: 40 }, paper_bgcolor: "transparent", plot_bgcolor: "transparent", autosize: true, legend: { orientation: "h" } }}
            config={{ displayModeBar: false, responsive: true }}
            useResizeHandler
            style={{ width: "100%", height: 300 }}
          />
        </article>
        <article className="data-card">
          <h3>Trạng thái khoản phải thu</h3>
          <Plot
            data={[{ type: "pie", hole: 0.62, labels: paymentLabels, values: paymentLabels.map((label) => data.payment_status_counts[label]), marker: { colors: ["#28795b", "#e2a536", "#be5a4d", "#65766e"] } }]}
            layout={{ margin: { l: 10, r: 10, t: 20, b: 20 }, paper_bgcolor: "transparent", autosize: true, showlegend: true }}
            config={{ displayModeBar: false, responsive: true }}
            useResizeHandler
            style={{ width: "100%", height: 300 }}
          />
        </article>
      </div>
      <article className="data-card">
        <div className="data-card__header"><h3>Nhóm đối soát</h3><span className="count-pill">{groups.length}</span></div>
        <div className="table-wrap"><table><thead><tr><th>Loại</th><th>Orders</th><th>Bank rows</th><th>Link</th><th>Rule</th><th>Giải thích</th></tr></thead><tbody>{groups.slice(0, 30).map((group) => <tr key={group.group_id}><td>{group.group_type}</td><td>{group.order_ids.join(", ")}</td><td>{group.bank_txn_ids.join(", ")}</td><td><span className={`tag tag-${group.link_status.toLowerCase()}`}>{group.link_status}</span></td><td>{group.evidence.rule_id}</td><td>{group.evidence.explanation_vi}</td></tr>)}</tbody></table></div>
      </article>
      <article className="data-card">
        <div className="data-card__header"><h3>Ngoại lệ và residual</h3><span className="count-pill">{exceptions.length}</span></div>
        <div className="table-wrap"><table><thead><tr><th>Reason</th><th>Orders</th><th>Bank rows</th><th>Risk amount</th></tr></thead><tbody>{exceptions.slice(0, 30).map((item) => <tr key={item.exception_id}><td>{item.reason_codes.join(", ")}</td><td>{item.order_ids.join(", ") || "—"}</td><td>{item.bank_txn_ids.join(", ") || "—"}</td><td>{formatMoney(item.risk_amount_minor, currency)}</td></tr>)}</tbody></table></div>
      </article>
    </div>
  );
}
