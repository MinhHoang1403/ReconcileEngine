import { useEffect, useState } from "react";
import { api } from "./api/client";
import { fetchHealth } from "./api/health";
import { AppHeader } from "./components/AppHeader";
import { Dashboard } from "./components/Dashboard";
import { HealthGate } from "./components/HealthGate";
import { ImportSummary } from "./components/ImportSummary";
import { MappingEditor } from "./components/MappingEditor";
import { NormalizedPreview } from "./components/NormalizedPreview";
import { ProgressStepper, type WorkflowStep } from "./components/ProgressStepper";
import { RawPreview } from "./components/RawPreview";
import { SourceWorkspace } from "./components/SourceWorkspace";
import type { BankRow, DashboardData, ExceptionRow, ExplorerTotals, GroupRow, HealthIssue, HealthResponse, Inspection, MappingState, OrderRow } from "./types";
import "./styles.css";

const importQuestions: Record<string, string> = {
  STRUCTURE_REQUIRES_CONFIRMATION: "Hãy kiểm tra đúng trang tính và dòng tiêu đề của file.",
  SOURCE_REQUIRES_CONFIRMATION: "Loại nguồn này cần xác nhận ý nghĩa trước khi đối soát; hệ thống không tự gộp các dòng.",
  MAPPING_REQUIRES_CONFIRMATION: "Hãy xác nhận những cột còn chưa rõ bên dưới. Các cột đã nhận diện được thu gọn.",
  CURRENCY_REQUIRES_CONFIRMATION: "Chưa xác định được một loại tiền duy nhất. Hãy xác nhận loại tiền của hai file.",
  MONEY_FORMAT_REQUIRES_CONFIRMATION: "Hãy xác nhận dấu phân cách số tiền. Ví dụ 1.000 có thể được hiểu khác nhau; hệ thống không tự đoán.",
  DATE_FORMAT_REQUIRES_CONFIRMATION: "Hãy chọn cách đọc ngày/tháng trong file để không đảo nhầm ngày.",
};

function inspectionDefaults(value: Inspection): Inspection {
  const fallbackAnalysis = (selected: Record<string, string>, requiredTotal: number) => ({
    suggestions: Object.entries(selected).map(([canonical_target, source_column]) => ({
      canonical_target, source_column, transformation: { type: "DIRECT" }, heuristic_score: 0,
      confidence: "LOW" as const, reasons: ["API chưa cung cấp đủ bằng chứng; cần xác nhận cột nguồn"], competitors: [],
      sample_before: [], sample_after: [], status: "needs-review" as const,
    })),
    selected_mapping: {},
    selected_transformations: {},
    required_total: requiredTotal,
    required_auto_selected: 0,
    required_needs_review: requiredTotal,
    required_unsupported: 0,
  });
  const fallbackStructure = (columns: string[]) => ({
    status: "AUTO_SELECTED" as const,
    reasons: ["Cấu trúc tiêu chuẩn"],
    selected: { sheet_name: null, delimiter: ",", header_row_number: 1, header_depth: 1, columns },
  });
  return {
    ...value,
    mapping_suggestions: value.mapping_suggestions ?? {
      orders: fallbackAnalysis(value.suggested_mapping.order_columns, 3),
      bank_transactions: fallbackAnalysis(value.suggested_mapping.bank_columns, 5),
    },
    detected_structure: value.detected_structure ?? {
      orders: fallbackStructure(value.raw_eda.orders.columns),
      bank_transactions: fallbackStructure(value.raw_eda.bank_transactions.columns),
    },
    import_profile: value.import_profile ?? {
      schema_fingerprint: "",
      schema_version: "",
      recognized: {
        orders: { key: "GENERIC_RECEIVABLE", name: "Khoản phải thu thông dụng", status: "RECOGNIZED", reasons: [] },
        bank_transactions: { key: "GENERIC_BANK_STATEMENT", name: "Sao kê ngân hàng thông dụng", status: "RECOGNIZED", reasons: [] },
      },
      saved_profile: null,
      applied: false,
    },
  };
}

const initialMapping = (inspection: Inspection): MappingState => {
  if (inspection.import_profile.saved_profile) return inspection.import_profile.saved_profile.mapping_snapshot;
  return {
  order_columns: { ...inspection.mapping_suggestions.orders.selected_mapping },
  bank_columns: { ...inspection.mapping_suggestions.bank_transactions.selected_mapping },
  currency: "VND",
  source_profile: "BANK_CREDIT",
  date_format: "AUTO",
  decimal_separator: ".",
  thousand_separator: ",",
  order_defaults: { order_status: "ELIGIBLE" },
  bank_defaults: {},
  confirmed_structure: Object.values(inspection.detected_structure).every((item) => item.status === "AUTO_SELECTED"),
  order_date_format: "AUTO",
  bank_date_format: "AUTO",
  order_transformations: inspection.mapping_suggestions.orders.selected_transformations,
  bank_transformations: inspection.mapping_suggestions.bank_transactions.selected_transformations,
  transformation_version: "smart-import-2026-10-16",
  confirmed_ambiguities: [],
  import_profile_id: null,
  import_profile_schema_version: null,
}; };

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
  const [workbookFile, setWorkbookFile] = useState<File | null>(null);
  const [uploadMode, setUploadMode] = useState<"files" | "workbook">("files");
  const [ordersSheet, setOrdersSheet] = useState("");
  const [bankSheet, setBankSheet] = useState("");
  const [saveProfile, setSaveProfile] = useState(false);
  const [profileName, setProfileName] = useState("");
  const [busy, setBusy] = useState(false);
  const [mappingValid, setMappingValid] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [normalizedPreviewOpen, setNormalizedPreviewOpen] = useState(false);
  const [sourceDetailsOpen, setSourceDetailsOpen] = useState(false);

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

  async function acceptInspection(value: Inspection) {
    const prepared = inspectionDefaults(value);
    setInspection(prepared);
    const nextMapping = prepared.automatic_mapping ?? initialMapping(prepared);
    setMapping(nextMapping);
    setMappingValid(false);
    setHealth(null);
    setSaveProfile(false);
    setProfileName("");
    setNormalizedPreviewOpen(false);
    setSourceDetailsOpen(false);
    if (prepared.automatic_mapping) {
      try {
        const checked = await api.confirmMapping(prepared.session_id, nextMapping);
        setHealth(checked);
        setStep("health");
      } catch (caught) {
        setStep("mapping");
        throw caught;
      }
    } else setStep("mapping");
  }

  async function loadRun(id: string) {
    const run = await api.run(id);
    const revision = run.effective_revision;
    const [summary, groupPage, exceptionPage, orderPage, bankPage] = await Promise.all([
      api.dashboard(id, revision), api.groups(id, 1, 50, revision), api.exceptions(id, 1, 50, revision),
      api.orders(id, 1, 50, revision), api.bankTransactions(id, 1, 50, revision),
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
        const next = await api.orders(runId, page, 50, dashboard?.effective_revision);
        setOrders((items) => [...items, ...next.items]);
      }
      if (kind === "bank") {
        const next = await api.bankTransactions(runId, page, 50, dashboard?.effective_revision);
        setBankTransactions((items) => [...items, ...next.items]);
      }
      if (kind === "groups") {
        const next = await api.groups(runId, page, 50, dashboard?.effective_revision);
        setGroups((items) => [...items, ...next.items]);
      }
      if (kind === "exceptions") {
        const next = await api.exceptions(runId, page, 50, dashboard?.effective_revision);
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
    setWorkbookFile(null);
    setUploadMode("files");
    setOrdersSheet("");
    setBankSheet("");
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
            serviceReady={serviceReady} busy={busy} ordersFile={ordersFile} bankFile={bankFile} workbookFile={workbookFile} uploadMode={uploadMode} ordersSheet={ordersSheet} bankSheet={bankSheet} reopenId={reopenId}
            onOrdersFile={setOrdersFile} onBankFile={setBankFile} onWorkbookFile={setWorkbookFile} onUploadMode={setUploadMode} onOrdersSheet={setOrdersSheet} onBankSheet={setBankSheet} onReopenId={setReopenId}
            onUpload={() => {
              if (uploadMode === "files" && ordersFile && bankFile) void action(() => api.inspectFiles(ordersFile, bankFile), acceptInspection);
              if (uploadMode === "workbook" && workbookFile) void action(() => api.inspectWorkbook(workbookFile, ordersSheet, bankSheet), acceptInspection);
            }}
            onDemo={() => void action(api.createDemo, acceptInspection)} onReopen={() => void reopenRun()}
          />
        )}

        {step === "mapping" && inspection && mapping && (
          <section className="page-section stack" aria-labelledby="mapping-title">
            <div className="section-heading">
              <div><p className="eyebrow">KIỂM TRA CẤU TRÚC DỮ LIỆU</p><h1 id="mapping-title">Kiểm tra và chuẩn hóa dữ liệu</h1><p>Hệ thống đã chuẩn bị những phần nhận diện chắc chắn. Bạn chỉ cần tập trung vào các mục còn mơ hồ hoặc chưa đủ thông tin.</p></div>
              <button className="text-button" type="button" onClick={reset}>Chọn lại nguồn</button>
            </div>
            <ImportSummary inspection={inspection} mapping={mapping} onChange={setMapping} />
            {!!inspection.automation_reasons?.length && <aside className="gate-callout blocked" role="status"><strong>Một vài chi tiết cần bạn xác nhận</strong><ul>{inspection.automation_reasons.map((reason) => <li key={reason}>{importQuestions[reason] ?? "Hãy kiểm tra cách đọc dữ liệu trước khi tiếp tục."}</li>)}</ul></aside>}
            <MappingEditor compact showParsing={inspection.automation_reasons?.some((reason) => ["CURRENCY_REQUIRES_CONFIRMATION", "MONEY_FORMAT_REQUIRES_CONFIRMATION", "DATE_FORMAT_REQUIRES_CONFIRMATION"].includes(reason))} mapping={mapping} ordersEda={inspection.raw_eda.orders} bankEda={inspection.raw_eda.bank_transactions} suggestions={inspection.mapping_suggestions} onChange={setMapping} onValidityChange={setMappingValid} />
            <details className="surface import-details"><summary>Xem dữ liệu gốc</summary><div className="preview-grid"><RawPreview title="Danh sách đơn hàng cần thu tiền" data={inspection.raw_eda.orders} /><RawPreview title="Danh sách giao dịch thanh toán" data={inspection.raw_eda.bank_transactions} /></div></details>
            <details className="surface import-details" onToggle={(event) => setNormalizedPreviewOpen(event.currentTarget.open)}><summary>Xem trước dữ liệu sau chuẩn hóa</summary>{normalizedPreviewOpen && <NormalizedPreview sessionId={inspection.session_id} mapping={mapping} enabled={mappingValid} />}</details>
            <div className="action-bar">
              <div className="confirmation-copy"><strong>Xác nhận cách đọc dữ liệu trước khi chuẩn hóa</strong><p>Mã định danh được giữ dạng chuỗi. Hệ thống không tự tạo mã, đổi cơ sở số tiền hoặc suy đoán ngày mơ hồ.</p>
                {!inspection.import_profile.applied && <label className="save-profile"><input type="checkbox" checked={saveProfile} onChange={(event) => setSaveProfile(event.target.checked)} /><span>Lưu cấu hình này cho file có cùng cấu trúc</span></label>}
                {saveProfile && <input aria-label="Tên cấu hình nhập liệu" value={profileName} onChange={(event) => setProfileName(event.target.value)} placeholder="Ví dụ: Sao kê ngân hàng A" />}
              </div>
              <button className="primary" type="button" disabled={busy || !mappingValid || (saveProfile && !profileName.trim()) || (!mapping.confirmed_structure && Object.values(inspection.detected_structure).some((item) => item.status === "NEEDS_REVIEW"))} onClick={() => void action(async () => {
                const value = await api.confirmMapping(inspection.session_id, mapping);
                if (saveProfile) await api.createImportProfile(inspection.session_id, profileName.trim());
                return value;
              }, (value) => { setHealth(value); setStep("health"); })}>
                {busy ? <><span className="spinner" aria-hidden="true" />Đang chuẩn hóa…</> : "Xác nhận và chuẩn hóa dữ liệu"}
              </button>
            </div>
          </section>
        )}

        {step === "health" && health && (
          <div className="stack">
            {inspection?.automatic_mapping && <div className="surface import-ready" role="status"><strong>Đã tự nhận diện và kiểm tra dữ liệu</strong><span>Giữ nguyên file gốc · {mapping?.currency} · chưa chạy đối soát hoặc chấp thuận đề xuất.</span></div>}
            <HealthGate health={health} busy={busy} onAcknowledge={() => void acknowledgeWarnings()} onExclude={(issue, reason) => void excludeIssue(issue, reason)} onRun={() => void runReconciliation()} onBack={() => setStep("mapping")} />
            {inspection && mapping && <details className="surface import-details" onToggle={(event) => setSourceDetailsOpen(event.currentTarget.open)}><summary>Xem file gốc và cách đọc dữ liệu</summary>{sourceDetailsOpen && <><div className="preview-grid"><RawPreview title="Danh sách đơn hàng cần thu tiền" data={inspection.raw_eda.orders} /><RawPreview title="Danh sách giao dịch thanh toán" data={inspection.raw_eda.bank_transactions} /></div><NormalizedPreview sessionId={inspection.session_id} mapping={mapping} enabled /></>}</details>}
          </div>
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
