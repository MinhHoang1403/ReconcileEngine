import { useEffect, useMemo, useState } from "react";
import { api } from "./api/client";
import { fetchHealth } from "./api/health";
import { Dashboard } from "./components/Dashboard";
import { MappingEditor } from "./components/MappingEditor";
import { RawPreview } from "./components/RawPreview";
import type {
  DashboardData,
  BankRow,
  ExceptionRow,
  GroupRow,
  HealthResponse,
  Inspection,
  MappingState,
  OrderRow,
} from "./types";
import "./styles.css";

type Step = "source" | "mapping" | "health" | "dashboard";

const initialMapping = (inspection: Inspection): MappingState => ({
  ...inspection.suggested_mapping,
  currency: "VND",
  source_profile: "BANK_CREDIT",
  date_format: "%Y-%m-%d",
  decimal_separator: ".",
  thousand_separator: ",",
  order_defaults: { order_status: "ELIGIBLE" },
  bank_defaults: {},
});

export function App() {
  const [serviceReady, setServiceReady] = useState(false);
  const [step, setStep] = useState<Step>("source");
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [mapping, setMapping] = useState<MappingState | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [groups, setGroups] = useState<GroupRow[]>([]);
  const [exceptions, setExceptions] = useState<ExceptionRow[]>([]);
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [bankTransactions, setBankTransactions] = useState<BankRow[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [reopenId, setReopenId] = useState("");
  const [ordersFile, setOrdersFile] = useState<File | null>(null);
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(() => setServiceReady(true))
      .catch(() => setServiceReady(false));
  }, []);

  const currentStep = useMemo(
    () => ({ source: 1, mapping: 2, health: 3, dashboard: 4 })[step],
    [step],
  );

  async function action<T>(
    operation: () => Promise<T>,
    onSuccess: (value: T) => void | Promise<void>,
  ) {
    setBusy(true);
    setError(null);
    try {
      await onSuccess(await operation());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Đã xảy ra lỗi không xác định");
    } finally {
      setBusy(false);
    }
  }

  function acceptInspection(value: Inspection) {
    setInspection(value);
    setMapping(initialMapping(value));
    setStep("mapping");
  }

  async function runReconciliation() {
    if (!inspection || !mapping) return;
    await action(
      () => api.createRun(inspection.session_id, mapping.currency),
      async (created) => {
        await loadRun(created.run_id);
      },
    );
  }

  async function loadRun(id: string) {
    const [summary, groupPage, exceptionPage, orderPage, bankPage] = await Promise.all([
      api.dashboard(id),
      api.groups(id),
      api.exceptions(id),
      api.orders(id),
      api.bankTransactions(id),
    ]);
    setRunId(id);
    setDashboard(summary);
    setGroups(groupPage.items);
    setExceptions(exceptionPage.items);
    setOrders(orderPage.items);
    setBankTransactions(bankPage.items);
    setStep("dashboard");
  }

  async function reopenRun() {
    const id = reopenId.trim();
    if (!id) return;
    await action(
      async () => {
        await api.run(id);
        return id;
      },
      loadRun,
    );
  }

  function reset() {
    setStep("source");
    setInspection(null);
    setMapping(null);
    setHealth(null);
    setDashboard(null);
    setRunId(null);
    setGroups([]);
    setExceptions([]);
    setOrders([]);
    setBankTransactions([]);
    setError(null);
  }

  async function excludeIssue(issue: HealthResponse["report"]["issues"][number]) {
    if (!inspection || !health || issue.source_rows.length === 0) return;
    const reason = window.prompt("Lý do loại trừ (bắt buộc, tối thiểu 3 ký tự):", issue.message_vi);
    if (!reason || reason.trim().length < 3) return;
    const additions = issue.source_rows.map((sourceRowNumber) => ({
      feed: issue.feed,
      source_row_number: sourceRowNumber,
      reason: reason.trim(),
    }));
    await action(
      () => api.resolveHealth(
        inspection.session_id,
        [...health.exclusions, ...additions],
        health.acknowledged_issue_codes,
      ),
      setHealth,
    );
  }

  async function acknowledgeWarnings() {
    if (!inspection || !health) return;
    const warningCodes = health.report.issues
      .filter((issue) => issue.severity === "WARNING")
      .map((issue) => issue.code);
    await action(
      () => api.resolveHealth(inspection.session_id, health.exclusions, warningCodes),
      setHealth,
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={reset}>SMARTRECON</button>
        <div className={`service-chip ${serviceReady ? "ready" : "offline"}`}>
          <span />{serviceReady ? "Hệ thống sẵn sàng" : "Mất kết nối backend"}
        </div>
      </header>

      <nav className="stepper" aria-label="Tiến trình đối soát">
        {["Nguồn dữ liệu", "Mapping & Health", "Chạy đối soát", "Dashboard & Export"].map(
          (label, index) => (
            <div className={currentStep >= index + 1 ? "step active" : "step"} key={label}>
              <span>{index + 1}</span><small>{label}</small>
            </div>
          ),
        )}
      </nav>

      {error && <div className="error-banner" role="alert">{error}</div>}

      {step === "source" && (
        <section className="hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">ĐỐI SOÁT HAI NGUỒN · BẢO TOÀN TIỀN</p>
            <h1>Biến giao dịch rời rạc thành bằng chứng có thể kiểm tra.</h1>
            <p className="intro">Upload khoản phải thu và giao dịch ngân hàng/PSP. SmartRecon chuẩn hóa, phát hiện nhóm gộp/chia, giữ nguyên residual và chỉ xác nhận khi đủ chứng cứ.</p>
            <button className="primary large" disabled={busy || !serviceReady} onClick={() => action(api.createDemo, acceptInspection)}>
              {busy ? "Đang chuẩn bị…" : "Chạy dữ liệu demo VND"}
            </button>
            <div className="reopen-panel"><input aria-label="Run ID" placeholder="Dán run ID để mở lại" value={reopenId} onChange={(event) => setReopenId(event.target.value)} /><button className="text-button" disabled={busy || !reopenId.trim()} onClick={reopenRun}>Mở run đã lưu</button></div>
          </div>
          <form className="upload-panel" onSubmit={(event) => {
            event.preventDefault();
            if (ordersFile && bankFile) action(() => api.inspectFiles(ordersFile, bankFile), acceptInspection);
          }}>
            <span className="overline">HOẶC DÙNG DỮ LIỆU CỦA BẠN</span>
            <h2>Hai feed CSV / XLSX</h2>
            <label className="file-drop"><span>Khoản phải thu</span><input type="file" accept=".csv,.xlsx" onChange={(event) => setOrdersFile(event.target.files?.[0] ?? null)} /><strong>{ordersFile?.name ?? "Chọn file orders"}</strong></label>
            <label className="file-drop"><span>Ngân hàng / PSP</span><input type="file" accept=".csv,.xlsx" onChange={(event) => setBankFile(event.target.files?.[0] ?? null)} /><strong>{bankFile?.name ?? "Chọn file bank"}</strong></label>
            <p className="muted">Tối đa 25 MB/file, 100.000 dòng. Raw input không bị ghi đè.</p>
            <button className="secondary" disabled={!ordersFile || !bankFile || busy}>Kiểm tra và preview</button>
          </form>
        </section>
      )}

      {step === "mapping" && inspection && mapping && (
        <section className="page-section stack">
          <div className="section-heading"><div><p className="eyebrow">RAW EDA → CANONICAL</p><h2>Xác nhận ý nghĩa từng cột</h2></div><button className="text-button" onClick={reset}>Chọn lại nguồn</button></div>
          <div className="two-column"><RawPreview title="Khoản phải thu" data={inspection.raw_eda.orders} /><RawPreview title="Ngân hàng / PSP" data={inspection.raw_eda.bank_transactions} /></div>
          <MappingEditor mapping={mapping} ordersEda={inspection.raw_eda.orders} bankEda={inspection.raw_eda.bank_transactions} onChange={setMapping} />
          <div className="action-bar"><p>Mapping chỉ có hiệu lực sau khi bạn xác nhận. ID được giữ dưới dạng chuỗi.</p><button className="primary" disabled={busy} onClick={() => action(() => api.confirmMapping(inspection.session_id, mapping), (value) => { setHealth(value); setStep("health"); })}>{busy ? "Đang chuẩn hóa…" : "Xác nhận mapping"}</button></div>
        </section>
      )}

      {step === "health" && inspection && mapping && health && (
        <section className="page-section stack">
          <div className="section-heading"><div><p className="eyebrow">STANDARDIZED EDA · HEALTH GATE</p><h2>{health.report.status === "READY" ? "Dữ liệu sẵn sàng đối soát" : "Cần xử lý lỗi chặn"}</h2></div><span className={`gate gate-${health.report.status.toLowerCase()}`}>{health.report.status}</span></div>
          <div className="health-summary"><div><strong>{health.report.blocking_count}</strong><span>Blocking</span></div><div><strong>{health.report.warning_count}</strong><span>Warnings</span></div><div><strong>{health.report.info_count}</strong><span>Info</span></div><div><strong>{String(health.standardized_eda.eligible_orders_count ?? 0)}</strong><span>Orders hợp lệ</span></div><div><strong>{String(health.standardized_eda.eligible_credit_count ?? 0)}</strong><span>Bank credits</span></div></div>
          <article className="data-card"><h3>Issues có lineage</h3><div className="issue-list">{health.report.issues.map((issue, index) => <div className="issue" key={`${issue.code}-${index}`}><span className={`severity severity-${issue.severity.toLowerCase()}`}>{issue.severity}</span><div><strong>{issue.code}</strong><p>{issue.message_vi}</p>{issue.source_rows.length > 0 && <small>Dòng nguồn: {issue.source_rows.join(", ")}</small>}{issue.severity === "BLOCKING" && issue.source_rows.length > 0 && <button className="text-button issue-action" disabled={busy} onClick={() => excludeIssue(issue)}>Loại trừ các dòng này có lý do</button>}</div></div>)}</div></article>
          <div className="action-bar"><p>Warnings vẫn được giữ trong exceptions; proposal không đi vào confirmed KPI.</p><div className="button-row">{health.report.warning_count > 0 && <button className="secondary" disabled={busy} onClick={acknowledgeWarnings}>{health.acknowledged_issue_codes.length > 0 ? "Đã ghi nhận warnings" : "Ghi nhận warnings"}</button>}<button className="primary" disabled={busy || health.report.status !== "READY"} onClick={runReconciliation}>{busy ? "Engine đang chạy…" : "Chạy đối soát"}</button></div></div>
        </section>
      )}

      {step === "dashboard" && dashboard && runId && (
        <section className="page-section stack">
          <div className="section-heading"><div><p className="eyebrow">RUN {runId.slice(0, 8)} · REVISION {dashboard.effective_revision}</p><h2>Kết quả đối soát</h2></div><div className="button-row"><a className="secondary link-button" href={`/api/runs/${runId}/exports?format=xlsx`}>Tải Excel</a><button className="text-button" onClick={reset}>Tạo phiên mới</button></div></div>
          <div className={`conservation ${dashboard.conservation.is_valid ? "valid" : "invalid"}`}>{dashboard.conservation.is_valid ? "✓ Bất biến bảo toàn tiền đã kiểm tra: 0 vi phạm" : `Có vi phạm: ${dashboard.conservation.violations.join(", ")}`}</div>
          <Dashboard data={dashboard} groups={groups} exceptions={exceptions} orders={orders} bankTransactions={bankTransactions} />
        </section>
      )}
    </main>
  );
}
