import { useMemo, useState } from "react";
import Plotly from "plotly.js/dist/plotly-basic.js";
import createPlotlyComponent from "react-plotly.js/factory";
import { api } from "../api/client";
import type {
  BankRow,
  DashboardData,
  ExceptionRow,
  ExplorerTotals,
  GroupDetail,
  GroupRow,
  OrderRow,
  TransactionDetail,
} from "../types";
import { asSafeMinorUnit, formatMoney } from "../utils/money";
import { buildLayerChartModel, buildPaymentStatusChartModel } from "./dashboardCharts";
import { ReconciliationReview } from "./ReconciliationReview";
import { TransactionDetailDrawer } from "./TransactionDetailDrawer";

const Plot = createPlotlyComponent(Plotly);
type ExplorerTab = keyof ExplorerTotals;

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
const linkStatus: Record<string, string> = {
  CONFIRMED: "Đã xác nhận",
  PROPOSED: "Đề xuất, chưa xác nhận",
  UNMATCHED: "Chưa tìm thấy đối ứng",
};
const groupType: Record<string, string> = {
  ONE_TO_ONE: "Một đơn – một giao dịch",
  MANY_ORDERS_ONE_BANK: "Nhiều đơn – một giao dịch",
  ONE_ORDER_MANY_BANKS: "Một đơn – nhiều giao dịch",
  AMBIGUOUS_CANDIDATES: "Nhiều phương án cần kiểm tra",
};
const reasonCode: Record<string, string> = {
  ORPHAN_BANK: "Chưa tìm thấy đơn hàng tương ứng",
  ORPHAN_INTERNAL: "Chưa tìm thấy giao dịch thanh toán tương ứng",
  NO_CONFIRMED_RECEIPT: "Chưa có khoản thu được xác nhận",
  PARTIAL_PAYMENT: "Thanh toán chưa đủ",
  OVERPAY_RESIDUAL: "Có tiền nhận chưa phân bổ",
  AMBIGUOUS_MATCH: "Có nhiều phương án đối chiếu",
  FUZZY_REFERENCE: "Tham chiếu gần giống, cần kiểm tra",
  AMBIGUOUS_CANDIDATES: "Có nhiều phương án đối chiếu",
  PROPOSED_BANK: "Có đề xuất nhưng chưa xác nhận",
  POSSIBLE_REIMPORT: "Có khả năng nhập lặp",
  DEBIT_EXCLUDED: "Giao dịch tiền ra không tham gia",
  CURRENCY_MISMATCH: "Khác loại tiền",
  REFERENCE_COLLISION: "Mã tham chiếu bị trùng",
};
const residualBucket: Record<string, string> = {
  UP_TO_1_PERCENT: "Đến 1% tổng phải thu",
  ONE_TO_FIVE_PERCENT: "Trên 1% đến 5%",
  OVER_FIVE_PERCENT: "Trên 5%",
};
const lagBucket: Record<string, string> = {
  BEFORE_ORDER: "Trước ngày đơn hàng",
  SAME_DAY: "Cùng ngày",
  ONE_DAY: "Sau 1 ngày",
  TWO_TO_THREE_DAYS: "Sau 2–3 ngày",
  OVER_THREE_DAYS: "Sau hơn 3 ngày",
};
function includesQuery(values: unknown[], query: string) {
  if (!query) return true;
  return values.some((value) => String(value ?? "").toLocaleLowerCase("vi").includes(query));
}

function normalizeGroupDetail(detail: GroupDetail): TransactionDetail {
  return {
    entity_type: "group",
    entity_id: detail.group_id,
    overview: detail.totals,
    orders: detail.order_records,
    bank_transactions: detail.bank_transaction_records,
    groups: [detail],
    allocations: detail.allocations,
    adjustments: detail.adjustments,
    candidates: detail.candidates,
    exceptions: detail.exceptions,
    selected_exception: null,
    guidance_vi: detail.link_status === "PROPOSED"
      ? "Đây là đề xuất ghép, chưa tạo khoản phân bổ tiền và chưa đi vào KPI đã xác nhận."
      : "Đối chiếu bản ghi nguồn, khoản phân bổ và bằng chứng trước khi kết luận.",
  };
}

export function Dashboard({
  data,
  groups,
  exceptions,
  orders,
  bankTransactions,
  totals,
  loadingMore,
  onLoadMore,
  onRevisionChanged,
  runId,
}: {
  data: DashboardData;
  groups: GroupRow[];
  exceptions: ExceptionRow[];
  orders: OrderRow[];
  bankTransactions: BankRow[];
  totals: ExplorerTotals;
  loadingMore: boolean;
  onLoadMore: (kind: ExplorerTab) => void | Promise<void>;
  onRevisionChanged: () => void | Promise<void>;
  runId: string;
}) {
  const [tab, setTab] = useState<ExplorerTab>("orders");
  const [query, setQuery] = useState("");
  const [groupStatus, setGroupStatus] = useState("ALL");
  const [detail, setDetail] = useState<TransactionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const currency = String(data.kpis.currency ?? "VND");
  const normalizedQuery = query.trim().toLocaleLowerCase("vi");
  const layerChart = buildLayerChartModel(data.layer_counts);
  const paymentChart = buildPaymentStatusChartModel(data);
  const analytics = data.analytics;
  const exceptionReasons = Object.entries(analytics.exception_reason_counts);
  const bridgeInputs = [
    data.kpis.expected_receivable_minor,
    data.kpis.confirmed_cash_allocated_minor,
    data.kpis.verified_adjustments_minor,
    data.kpis.outstanding_receivable_minor,
  ];
  const [expected, confirmed, adjustments, outstanding] = bridgeInputs.map(asSafeMinorUnit);
  const bridgeCanVerify = expected !== null && confirmed !== null && adjustments !== null && outstanding !== null;
  const bridgeValid = bridgeCanVerify && expected === confirmed + adjustments + outstanding;
  const moneyCards = [
    ["Tổng số tiền cần thu", "expected_receivable_minor", "Tổng giá trị các đơn hàng đủ điều kiện đối soát."],
    ["Tiền đã nhận và đối chiếu thành công", "confirmed_cash_allocated_minor", "Chỉ gồm tiền mặt đã được phân bổ bằng quan hệ xác nhận."],
    ["Điều chỉnh đã xác minh", "verified_adjustments_minor", "Khoản không phải tiền mặt, chỉ ghi nhận khi có chính sách và bằng chứng rõ ràng."],
    ["Số tiền chưa được xác nhận đã thu", "outstanding_receivable_minor", "Phần còn lại sau tiền đã phân bổ và điều chỉnh đã xác minh."],
    ["Tiền đã nhận nhưng chưa xác định được đơn hàng", "unapplied_bank_credit_minor", "Tiền ghi có đủ điều kiện nhưng chưa được phân bổ vào đơn hàng."],
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

  const loaded = { orders: orders.length, bank: bankTransactions.length, groups: groups.length, exceptions: exceptions.length };
  const visibleCount = { orders: filteredOrders.length, bank: filteredBank.length, groups: filteredGroups.length, exceptions: filteredExceptions.length }[tab];
  const tabs: { id: ExplorerTab; label: string }[] = [
    { id: "orders", label: "Đơn hàng cần thu" },
    { id: "bank", label: "Giao dịch thanh toán" },
    { id: "groups", label: "Nhóm đối chiếu" },
    { id: "exceptions", label: "Trường hợp cần kiểm tra" },
  ];

  async function openDetail(kind: ExplorerTab, id: string) {
    setDetailLoading(id);
    setDetailError(null);
    try {
      if (kind === "orders") setDetail(await api.orderDetail(runId, id, data.effective_revision));
      if (kind === "bank") setDetail(await api.bankTransactionDetail(runId, id, data.effective_revision));
      if (kind === "exceptions") setDetail(await api.exceptionDetail(runId, id, data.effective_revision));
      if (kind === "groups") setDetail(normalizeGroupDetail(await api.groupDetail(runId, id, data.effective_revision)));
    } catch (caught) {
      setDetailError(caught instanceof Error ? caught.message : "Không thể mở chi tiết giao dịch");
    } finally {
      setDetailLoading(null);
    }
  }

  function selectTab(next: ExplorerTab) {
    setTab(next);
    setQuery("");
    setDetailError(null);
  }

  const idButton = (kind: ExplorerTab, id: string) => (
    <button className="id-link" type="button" onClick={() => void openDetail(kind, id)} disabled={detailLoading === id}>
      {detailLoading === id ? "Đang mở…" : id}
    </button>
  );

  return (
    <div className="dashboard-stack">
      <section className="dashboard-section" aria-labelledby="overview-title">
        <div className="section-label"><span>A</span><div><h2 id="overview-title">Tổng quan kiểm soát</h2><p>Di chuột hoặc chạm vào từng chỉ số để xem cách tính. Đề xuất chưa xác nhận không được cộng vào các KPI tiền.</p></div></div>
        <div className="kpi-grid">
          {moneyCards.map(([label, key, explanation]) => (
            <article className="kpi-card" key={key} title={explanation}><span>{label}</span><strong>{formatMoney(data.kpis[key], currency)}</strong><small>{explanation}</small></article>
          ))}
          <article className="kpi-card"><span>Đơn hàng đã xác nhận thanh toán đủ</span><strong>{String(data.kpis.fully_settled_orders_count)}</strong><small>Đơn có bằng chứng đối chiếu xác nhận và nghĩa vụ đã được giải quyết đầy đủ.</small></article>
          <article className="kpi-card attention"><span>Trường hợp cần kiểm tra</span><strong>{String(data.kpis.unresolved_exceptions_count)}</strong><small>Các trường hợp chưa đủ bằng chứng hoặc còn chênh lệch.</small></article>
        </div>
        <div className={`kpi-bridge ${bridgeValid ? "valid" : "invalid"}`}>
          <strong>Đối chiếu tổng phải thu</strong>
          <span>{formatMoney(expected, currency)} = {formatMoney(confirmed, currency)} tiền đã nhận + {formatMoney(adjustments, currency)} điều chỉnh đã xác minh + {formatMoney(outstanding, currency)} còn phải thu</span>
          <small>{bridgeValid
            ? "Các thành phần khớp chính xác."
            : bridgeCanVerify
              ? "Các thành phần chưa khớp; cần kiểm tra dữ liệu nguồn."
              : "Không thể xác minh trên trình duyệt vì có giá trị thiếu hoặc vượt giới hạn số nguyên an toàn."}</small>
        </div>
      </section>

      <section className="dashboard-section" aria-labelledby="analysis-title">
        <div className="section-label"><span>B</span><div><h2 id="analysis-title">Phân tích kết quả</h2><p>Các chỉ số dưới đây cùng thuộc revision {data.effective_revision}; đề xuất chưa duyệt không được tính vào tiền đã xác nhận.</p></div></div>
        <div className="review-metric-grid" aria-label="Phân tích xác minh">
          <article><span>Đề xuất đang chờ</span><strong>{analytics.review_status_counts.OPEN ?? 0}</strong></article>
          <article><span>Đề xuất đã chấp thuận</span><strong>{analytics.review_status_counts.APPROVED ?? 0}</strong></article>
          <article><span>Đề xuất đã từ chối</span><strong>{analytics.review_status_counts.REJECTED ?? 0}</strong></article>
          <article><span>Quyết định đã hoàn tác</span><strong>{analytics.review_decision_counts.UNDO_ACTION ?? 0}</strong></article>
          <article><span>Tỷ lệ nhóm đã xác nhận</span><strong>{analytics.method_summary.confirmation_rate_percent.toLocaleString("vi-VN", { maximumFractionDigits: 2 })}%</strong><small>{analytics.method_summary.confirmed_groups}/{analytics.method_summary.total_relation_groups} nhóm; mẫu số gồm mọi nhóm quan hệ.</small></article>
        </div>
        <div className="chart-grid">
          <article className="surface chart-card" data-chart="matching-layers">
            <div className="chart-heading"><div><h3>Nhóm đối chiếu theo phương pháp</h3><p>Đơn vị là nhóm đối chiếu, không phải từng giao dịch ngân hàng. Đề xuất chưa xác nhận không tạo phân bổ và không đi vào KPI tiền.</p></div></div>
            <div className="chart-series-legend" aria-label="Chú giải biểu đồ phương pháp"><span><i className="legend-confirmed" />Đã xác nhận</span><span><i className="legend-proposed" />Đề xuất cần kiểm tra</span></div>
            {layerChart.isEmpty ? <p className="chart-empty">Chưa có nhóm đối chiếu hoặc đề xuất để hiển thị.</p> : <Plot
              data={[
                {
                  type: "bar", orientation: "h", name: "Đã xác nhận",
                  x: layerChart.rows.map((row) => row.confirmed), y: layerChart.rows.map((row) => row.tickLabel),
                  customdata: layerChart.rows.map((row) => row.label),
                  text: layerChart.rows.map((row) => row.confirmed > 0 ? String(row.confirmed) : ""), textposition: "outside", cliponaxis: false,
                  hovertemplate: "%{customdata}<br>Đã xác nhận: %{x:,d} nhóm<extra></extra>", marker: { color: "#176b4d" },
                },
                {
                  type: "bar", orientation: "h", name: "Đề xuất cần kiểm tra",
                  x: layerChart.rows.map((row) => row.proposed), y: layerChart.rows.map((row) => row.tickLabel),
                  customdata: layerChart.rows.map((row) => row.label),
                  text: layerChart.rows.map((row) => row.proposed > 0 ? String(row.proposed) : ""), textposition: "outside", cliponaxis: false,
                  hovertemplate: "%{customdata}<br>Đề xuất cần kiểm tra: %{x:,d} nhóm<extra></extra>", marker: { color: "#d49320" },
                },
              ]}
              layout={{ barmode: "group", margin: { l: 190, r: 34, t: 10, b: 48 }, xaxis: { title: { text: "Số nhóm đối chiếu" }, rangemode: "tozero", tickmode: "auto", nticks: 6, tickformat: ",d", automargin: true }, yaxis: { automargin: true, autorange: "reversed" }, paper_bgcolor: "transparent", plot_bgcolor: "transparent", autosize: true, showlegend: false, bargap: 0.24, font: { family: "Segoe UI, Arial, sans-serif", color: "#44534c", size: 11 } }}
              config={{ displayModeBar: false, responsive: true }} useResizeHandler style={{ width: "100%", height: 360 }}
            />}
          </article>
          <article className="surface chart-card" data-chart="payment-statuses">
            <div className="chart-heading"><div><h3>Tình trạng thanh toán của các đơn hàng</h3><p>Mẫu số: {paymentChart.eligibleTotal.toLocaleString("vi-VN")} đơn hàng đủ điều kiện đối soát.</p></div></div>
            {paymentChart.isEmpty ? <p className="chart-empty">Chưa có đơn hàng đủ điều kiện để thống kê tình trạng thanh toán.</p> : <>
              <Plot
                data={[{
                  type: "pie", hole: 0.62,
                  labels: paymentChart.rows.map((row) => row.label), values: paymentChart.rows.map((row) => row.count),
                  customdata: paymentChart.rows.map((row) => row.legendLabel),
                  marker: { colors: paymentChart.rows.map((row) => row.color) },
                  textinfo: "none", sort: false, hovertemplate: "%{customdata}<extra></extra>",
                }]}
                layout={{ margin: { l: 8, r: 8, t: 8, b: 8 }, paper_bgcolor: "transparent", autosize: true, showlegend: false, font: { family: "Segoe UI, Arial, sans-serif", color: "#44534c" } }}
                config={{ displayModeBar: false, responsive: true }} useResizeHandler style={{ width: "100%", height: 250 }}
              />
              <div className="payment-legend" aria-label="Chú giải tình trạng thanh toán">{paymentChart.rows.map((row) => <div key={row.code}><i style={{ backgroundColor: row.color }} /><span>{row.label}</span><strong>{row.count.toLocaleString("vi-VN")} đơn ({row.percentage.toLocaleString("vi-VN", { maximumFractionDigits: 1 })}%)</strong></div>)}</div>
            </>}
            {paymentChart.notEligibleCount > 0 && <p className="chart-note">Không đủ điều kiện: {paymentChart.notEligibleCount.toLocaleString("vi-VN")} đơn, không thuộc mẫu số biểu đồ.</p>}
            {!paymentChart.isConsistent && <p className="chart-warning" role="status">Tổng trạng thái ({paymentChart.countedTotal.toLocaleString("vi-VN")}) chưa khớp số đơn đủ điều kiện ({paymentChart.eligibleTotal.toLocaleString("vi-VN")}).</p>}
          </article>
        </div>
        <div className="analytics-detail-grid">
          <article className="surface analytics-card">
            <h3>Quan hệ thanh toán đã xác nhận</h3>
            <p>Đơn vị: nhóm đối chiếu đã xác nhận.</p>
            <dl><div><dt>Thanh toán gộp</dt><dd>{analytics.confirmed_group_type_counts.MANY_ORDERS_ONE_BANK ?? 0}</dd></div><div><dt>Thanh toán nhiều lần</dt><dd>{analytics.confirmed_group_type_counts.ONE_ORDER_MANY_BANKS ?? 0}</dd></div><div><dt>Một–một</dt><dd>{analytics.confirmed_group_type_counts.ONE_TO_ONE ?? 0}</dd></div></dl>
          </article>
          <article className="surface analytics-card">
            <h3>Phân bố phần tiền chưa giải quyết</h3>
            <p>Ngưỡng theo tỷ lệ trên tổng phải thu {formatMoney(analytics.residual_distribution.denominator_minor, currency)}; hai sổ được trình bày riêng để tránh cộng trùng.</p>
            <table><thead><tr><th>Mức</th><th>Đơn còn phải thu</th><th>Tiền ngân hàng chưa phân bổ</th></tr></thead><tbody>{analytics.residual_distribution.order_outstanding.map((bucket, index) => <tr key={bucket.bucket}><td>{residualBucket[bucket.bucket] ?? bucket.bucket}</td><td>{bucket.count} · {formatMoney(bucket.amount_minor, currency)}</td><td>{analytics.residual_distribution.bank_unapplied[index]?.count ?? 0} · {formatMoney(analytics.residual_distribution.bank_unapplied[index]?.amount_minor ?? 0, currency)}</td></tr>)}</tbody></table>
          </article>
          <article className="surface analytics-card">
            <h3>Nguyên nhân ngoại lệ phổ biến</h3>
            <p>Đơn vị: số mã lý do trên các trường hợp chưa giải quyết.</p>
            {exceptionReasons.length ? <ol>{exceptionReasons.slice(0, 6).map(([code, count]) => <li key={code}><span>{reasonCode[code] ?? code}</span><strong>{count}</strong></li>)}</ol> : <p>Không có ngoại lệ trong revision này.</p>}
          </article>
          <article className="surface analytics-card">
            <h3>Độ trễ giao dịch đã xác nhận</h3>
            <p>Đơn vị quan sát: {analytics.confirmed_lag.observations} cặp phân bổ đơn hàng–giao dịch; trung vị {analytics.confirmed_lag.median_days === null ? "—" : `${analytics.confirmed_lag.median_days.toLocaleString("vi-VN")} ngày`}.</p>
            <ol>{analytics.confirmed_lag.buckets.map((bucket) => <li key={bucket.bucket}><span>{lagBucket[bucket.bucket] ?? bucket.bucket}</span><strong>{bucket.count}</strong></li>)}</ol>
          </article>
        </div>
      </section>

      <ReconciliationReview
        runId={runId}
        currency={currency}
        effectiveRevision={data.effective_revision}
        onOpenGroup={(groupId) => openDetail("groups", groupId)}
        onRevisionChanged={onRevisionChanged}
      />

      <section className="dashboard-section" aria-labelledby="explorer-title">
        <div className="section-label"><span>D</span><div><h2 id="explorer-title">Tra cứu chi tiết</h2><p>Tìm kiếm trong phần dữ liệu đã tải. Chọn mã hoặc dòng để xem nguồn, bằng chứng và phân bổ tiền.</p></div></div>
        <article className="surface explorer-card">
          <div className="explorer-tabs" role="tablist" aria-label="Loại dữ liệu tra cứu">
            {tabs.map((item) => <button key={item.id} type="button" role="tab" aria-selected={tab === item.id} className={tab === item.id ? "active" : ""} onClick={() => selectTab(item.id)}>{item.label}<span>{totals[item.id]}</span></button>)}
          </div>
          <div className="explorer-tools">
            <label className="search-field"><span className="sr-only">Tìm kiếm trong phần đã tải</span><span aria-hidden="true">⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm theo mã, trạng thái hoặc quy tắc…" /></label>
            {tab === "groups" && <label className="filter-field"><span className="sr-only">Lọc trạng thái nhóm</span><select value={groupStatus} onChange={(event) => setGroupStatus(event.target.value)}><option value="ALL">Tất cả trạng thái</option><option value="CONFIRMED">Đã xác nhận</option><option value="PROPOSED">Đề xuất, chưa xác nhận</option></select></label>}
            <span className="loaded-count">Hiển thị {visibleCount} · Đã tải {loaded[tab]} / tổng {totals[tab]}</span>
          </div>
          {detailError && <div className="inline-error" role="alert">{detailError}</div>}
          <div className="table-wrap explorer-table">
            {tab === "orders" && <table><caption className="sr-only">Đơn hàng cần thu</caption><thead><tr><th>Mã đơn hàng</th><th>Số tiền cần thu</th><th>Tiền đã phân bổ</th><th>Còn phải thu</th><th>Trạng thái</th></tr></thead><tbody>{filteredOrders.map((row) => <tr key={row.order_id} className="clickable-row" onDoubleClick={() => void openDetail("orders", row.order_id)}><td className="id-cell">{idButton("orders", row.order_id)}</td><td>{formatMoney(row.expected_amount_minor, currency)}</td><td>{formatMoney(row.allocated_cash_minor, currency)}</td><td>{formatMoney(row.outstanding_minor, currency)}</td><td><span className={`status-tag status-${row.payment_status.toLowerCase()}`} title={row.payment_status}>{paymentStatus[row.payment_status] ?? row.payment_status}</span></td></tr>)}</tbody></table>}
            {tab === "bank" && <table><caption className="sr-only">Giao dịch thanh toán</caption><thead><tr><th>Mã giao dịch</th><th>Số tiền</th><th>Tiền đã phân bổ</th><th>Tiền chưa phân bổ</th><th>Chiều giao dịch</th></tr></thead><tbody>{filteredBank.map((row) => <tr key={row.bank_txn_id} className="clickable-row" onDoubleClick={() => void openDetail("bank", row.bank_txn_id)}><td className="id-cell">{idButton("bank", row.bank_txn_id)}</td><td>{formatMoney(row.posted_amount_minor, currency)}</td><td>{formatMoney(row.allocated_cash_minor, currency)}</td><td>{formatMoney(row.unapplied_minor, currency)}</td><td>{row.direction === "CREDIT" ? "Tiền vào" : row.direction === "DEBIT" ? "Tiền ra" : row.direction}</td></tr>)}</tbody></table>}
            {tab === "groups" && <table><caption className="sr-only">Nhóm đối chiếu</caption><thead><tr><th>Kiểu quan hệ</th><th>Đơn hàng</th><th>Giao dịch thanh toán</th><th>Trạng thái</th><th>Phương pháp</th><th>Giải thích</th></tr></thead><tbody>{filteredGroups.map((group) => <tr key={group.group_id} className="clickable-row" onClick={() => void openDetail("groups", group.group_id)}><td>{groupType[group.group_type] ?? group.group_type}</td><td>{group.order_ids.join(", ")}</td><td>{group.bank_txn_ids.join(", ")}</td><td><span className={`status-tag status-${group.link_status.toLowerCase()}`} title={group.link_status}>{linkStatus[group.link_status] ?? group.link_status}</span></td><td>{group.evidence.rule_id}</td><td>{group.evidence.explanation_vi}</td></tr>)}</tbody></table>}
            {tab === "exceptions" && <table><caption className="sr-only">Trường hợp cần kiểm tra</caption><thead><tr><th>Lý do cần kiểm tra</th><th>Đơn hàng</th><th>Giao dịch thanh toán</th><th>Giá trị cần kiểm tra</th></tr></thead><tbody>{filteredExceptions.map((item) => <tr key={item.exception_id} className="clickable-row" onClick={() => void openDetail("exceptions", item.exception_id)}><td>{item.reason_codes.map((code) => reasonCode[code] ?? code).join(" · ")}</td><td>{item.order_ids.join(", ") || "—"}</td><td>{item.bank_txn_ids.join(", ") || "—"}</td><td>{formatMoney(item.risk_amount_minor, currency)}</td></tr>)}</tbody></table>}
          </div>
          {visibleCount === 0 && <p className="empty-state">Không tìm thấy bản ghi phù hợp trong phần dữ liệu đã tải.</p>}
          {loaded[tab] < totals[tab] && <div className="load-more"><button className="secondary" type="button" disabled={loadingMore} onClick={() => void onLoadMore(tab)}>{loadingMore ? "Đang tải…" : `Tải thêm (${totals[tab] - loaded[tab]} bản ghi còn lại)`}</button></div>}
        </article>
      </section>

      <section className="dashboard-section" aria-labelledby="export-title">
        <div className="section-label"><span>E</span><div><h2 id="export-title">Xuất báo cáo và truy vết</h2><p>Tải báo cáo Excel gồm tổng quan, dữ liệu nguồn chuẩn hóa, phân bổ, đề xuất và thông tin truy vết.</p></div></div>
        <article className={`surface export-panel ${data.conservation.is_valid ? "valid" : "invalid"}`}>
          <div className="export-status"><span aria-hidden="true">{data.conservation.is_valid ? "✓" : "!"}</span><div><strong>{data.conservation.is_valid ? "Bảo toàn tiền đã được xác minh" : "Phát hiện vi phạm bảo toàn tiền"}</strong><p>{data.conservation.is_valid ? "Không có phân bổ trùng hoặc phần chênh lệch bị mất." : data.conservation.violations.join(", ")}</p></div></div>
          <dl><div><dt>Mã phiên</dt><dd>{runId}</dd></div><div><dt>Lần sửa</dt><dd>{data.effective_revision}</dd></div><div><dt>Định dạng</dt><dd>Excel (.xlsx)</dd></div></dl>
          <a className="primary link-button" href={`/api/runs/${runId}/exports?format=xlsx&expected_revision=${data.effective_revision}`}>Tải báo cáo Excel</a>
        </article>
      </section>

      {detail && <TransactionDetailDrawer detail={detail} currency={currency} onClose={() => setDetail(null)} />}
    </div>
  );
}
