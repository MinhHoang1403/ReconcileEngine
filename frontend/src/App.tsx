import { useEffect, useState } from "react";
import { api } from "./api/client";
import { fetchHealth } from "./api/health";
import { AppHeader } from "./components/AppHeader";
import { Dashboard } from "./components/Dashboard";
import { HealthGate } from "./components/HealthGate";
import { MappingEditor } from "./components/MappingEditor";
import { ProgressStepper, type WorkflowStep } from "./components/ProgressStepper";
import { RawPreview } from "./components/RawPreview";
import { SourceWorkspace } from "./components/SourceWorkspace";
import type { BankRow, DashboardData, ExceptionRow, ExplorerTotals, GroupRow, HealthIssue, HealthResponse, Inspection, MappingState, OrderRow } from "./types";
import "./styles.css";

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
  const [step, setStep] = useState<WorkflowStep>("source");
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [mapping, setMapping] = useState<MappingState | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [groups, setGroups] = useState<GroupRow[]>([]);
  const [exceptions, setExceptions] = useState<ExceptionRow[]>([]);
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [bankTransactions, setBankTransactions] = useState<BankRow[]>([]);
  const [explorerTotals, setExplorerTotals] = useState<ExplorerTotals>({ orders: 0, bank: 0, groups: 0, exceptions: 0 });
  const [loadedAt, setLoadedAt] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [reopenId, setReopenId] = useState("");
  const [ordersFile, setOrdersFile] = useState<File | null>(null);
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [mappingValid, setMappingValid] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth().then(() => setServiceReady(true)).catch(() => setServiceReady(false));
  }, []);

  useEffect(() => {
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  }, [step]);

  async function action<T>(operation: () => Promise<T>, onSuccess: (value: T) => void | Promise<void>) {
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
    setHealth(null);
    setStep("mapping");
  }

  async function loadRun(id: string) {
    const [run, summary, groupPage, exceptionPage, orderPage, bankPage] = await Promise.all([
      api.run(id), api.dashboard(id), api.groups(id), api.exceptions(id), api.orders(id), api.bankTransactions(id),
    ]);
    setRunId(id);
    setDashboard(summary);
    setGroups(groupPage.items);
    setExceptions(exceptionPage.items);
    setOrders(orderPage.items);
    setBankTransactions(bankPage.items);
    setExplorerTotals({ orders: orderPage.total, bank: bankPage.total, groups: groupPage.total, exceptions: exceptionPage.total });
    setLoadedAt(run.completed_at ?? run.created_at);
    setStep("dashboard");
  }

  async function loadMore(kind: keyof ExplorerTotals) {
    if (!runId || loadingMore) return;
    const current = { orders, bank: bankTransactions, groups, exceptions }[kind];
    if (current.length >= explorerTotals[kind]) return;
    setLoadingMore(true);
    setError(null);
    try {
      const page = Math.floor(current.length / 50) + 1;
      if (kind === "orders") {
        const next = await api.orders(runId, page);
        setOrders((items) => [...items, ...next.items]);
      }
      if (kind === "bank") {
        const next = await api.bankTransactions(runId, page);
        setBankTransactions((items) => [...items, ...next.items]);
      }
      if (kind === "groups") {
        const next = await api.groups(runId, page);
        setGroups((items) => [...items, ...next.items]);
      }
      if (kind === "exceptions") {
        const next = await api.exceptions(runId, page);
        setExceptions((items) => [...items, ...next.items]);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể tải thêm dữ liệu");
    } finally {
      setLoadingMore(false);
    }
  }

  async function runReconciliation() {
    if (!inspection || !mapping) return;
    await action(() => api.createRun(inspection.session_id, mapping.currency), (created) => loadRun(created.run_id));
  }

  async function reopenRun() {
    const id = reopenId.trim();
    if (!id) return;
    await action(() => Promise.resolve(id), loadRun);
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
    setExplorerTotals({ orders: 0, bank: 0, groups: 0, exceptions: 0 });
    setLoadedAt(null);
    setOrdersFile(null);
    setBankFile(null);
    setError(null);
  }

  async function excludeIssue(issue: HealthIssue, reason: string) {
    if (!inspection || !health || issue.source_rows.length === 0 || reason.length < 3) return;
    const additions = issue.source_rows.map((sourceRowNumber) => ({ feed: issue.feed, source_row_number: sourceRowNumber, reason }));
    await action(
      () => api.resolveHealth(inspection.session_id, [...health.exclusions, ...additions], health.acknowledged_issue_codes),
      setHealth,
    );
  }

  async function acknowledgeWarnings() {
    if (!inspection || !health) return;
    const warningCodes = health.report.issues.filter((issue) => issue.severity === "WARNING").map((issue) => issue.code);
    await action(() => api.resolveHealth(inspection.session_id, health.exclusions, warningCodes), setHealth);
  }

  return (
    <div className="app-frame">
      <AppHeader serviceReady={serviceReady} onReset={reset} />
      <main className="app-shell">
        <ProgressStepper current={step} />
        {error && <div className="error-banner" role="alert"><span>{error}</span><button type="button" onClick={() => setError(null)} aria-label="Đóng thông báo lỗi">×</button></div>}

        {step === "source" && (
          <SourceWorkspace
            serviceReady={serviceReady} busy={busy} ordersFile={ordersFile} bankFile={bankFile} reopenId={reopenId}
            onOrdersFile={setOrdersFile} onBankFile={setBankFile} onReopenId={setReopenId}
            onUpload={() => { if (ordersFile && bankFile) void action(() => api.inspectFiles(ordersFile, bankFile), acceptInspection); }}
            onDemo={() => void action(api.createDemo, acceptInspection)} onReopen={() => void reopenRun()}
          />
        )}

        {step === "mapping" && inspection && mapping && (
          <section className="page-section stack" aria-labelledby="mapping-title">
            <div className="section-heading">
              <div><p className="eyebrow">KIỂM TRA CẤU TRÚC DỮ LIỆU</p><h1 id="mapping-title">Kiểm tra và chuẩn hóa dữ liệu</h1><p>Tên cột trong mỗi hệ thống có thể khác nhau. Hãy ghép từng cột nguồn với đúng ý nghĩa nghiệp vụ trước khi chuẩn hóa.</p></div>
              <button className="text-button" type="button" onClick={reset}>Chọn lại nguồn</button>
            </div>
            <div className="preview-grid"><RawPreview title="Danh sách đơn hàng cần thu tiền" data={inspection.raw_eda.orders} /><RawPreview title="Danh sách giao dịch thanh toán" data={inspection.raw_eda.bank_transactions} /></div>
            <MappingEditor mapping={mapping} ordersEda={inspection.raw_eda.orders} bankEda={inspection.raw_eda.bank_transactions} onChange={setMapping} onValidityChange={setMappingValid} />
            <div className="action-bar">
              <div><strong>Xác nhận cách ghép cột trước khi chuẩn hóa</strong><p>Mã định danh được giữ dạng chuỗi. Cột bắt buộc phải đủ và mỗi cột nguồn chỉ được dùng một lần.</p></div>
              <button className="primary" type="button" disabled={busy || !mappingValid} onClick={() => void action(() => api.confirmMapping(inspection.session_id, mapping), (value) => { setHealth(value); setStep("health"); })}>
                {busy ? <><span className="spinner" aria-hidden="true" />Đang chuẩn hóa…</> : "Chuẩn hóa dữ liệu"}
              </button>
            </div>
          </section>
        )}

        {step === "health" && health && (
          <HealthGate health={health} busy={busy} onAcknowledge={() => void acknowledgeWarnings()} onExclude={(issue, reason) => void excludeIssue(issue, reason)} onRun={() => void runReconciliation()} onBack={() => setStep("mapping")} />
        )}

        {step === "dashboard" && dashboard && runId && (
          <section className="page-section stack" aria-labelledby="dashboard-title">
            <div className="section-heading dashboard-heading">
              <div><p className="eyebrow">MÃ PHIÊN {runId.slice(0, 8)} · LẦN CẬP NHẬT {loadedAt ? new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(new Date(loadedAt)) : "—"}</p><h1 id="dashboard-title">Kết quả đối soát</h1><p>Tổng quan, phân tích và bằng chứng truy vết của phiên hiện tại.</p></div>
              <button className="secondary" type="button" onClick={reset}>Tạo phiên mới</button>
            </div>
            <Dashboard data={dashboard} groups={groups} exceptions={exceptions} orders={orders} bankTransactions={bankTransactions} totals={explorerTotals} loadingMore={loadingMore} onLoadMore={loadMore} onRevisionChanged={() => loadRun(runId)} runId={runId} />
          </section>
        )}
      </main>
    </div>
  );
}
