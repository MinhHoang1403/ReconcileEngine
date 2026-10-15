import { useMemo, useState } from "react";
import type { HealthIssue, HealthResponse } from "../types";

type Props = {
  health: HealthResponse;
  busy: boolean;
  onAcknowledge: () => void;
  onExclude: (issue: HealthIssue, reason: string) => void;
  onRun: () => void;
  onBack: () => void;
};

const severityOrder = { BLOCKING: 0, WARNING: 1, INFO: 2 } as const;
const severityLabels = { BLOCKING: "Chặn", WARNING: "Cảnh báo", INFO: "Thông tin" } as const;

export function HealthGate({ health, busy, onAcknowledge, onExclude, onRun, onBack }: Props) {
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const issues = useMemo(
    () => [...health.report.issues].sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]),
    [health.report.issues],
  );
  const ready = health.report.status === "READY";
  const warningsAcknowledged = health.report.warning_count > 0 && health.acknowledged_issue_codes.length > 0;

  function issueKey(issue: HealthIssue, index: number) {
    return `${issue.code}-${issue.feed}-${index}`;
  }

  return (
    <section className="page-section stack" aria-labelledby="health-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">CỔNG CHẤT LƯỢNG DỮ LIỆU</p>
          <h1 id="health-title">{ready ? "Dữ liệu sẵn sàng đối soát" : "Dữ liệu chưa thể đối soát"}</h1>
          <p>Kiểm tra lỗi chặn trước, sau đó ghi nhận cảnh báo để lưu dấu vết quyết định.</p>
        </div>
        <span className={`gate gate-${health.report.status.toLowerCase()}`}>
          {ready ? "Sẵn sàng" : "Đang bị chặn"}
        </span>
      </div>

      <div className={`gate-callout ${ready ? "ready" : "blocked"}`} role="status">
        <strong>{ready ? "Có thể chạy engine" : "Chưa thể chạy engine"}</strong>
        <span>
          {ready
            ? "Các lỗi chặn đã được xử lý. Cảnh báo còn lại vẫn được đưa vào báo cáo ngoại lệ."
            : "Hãy sửa dữ liệu nguồn hoặc loại trừ rõ từng dòng lỗi kèm lý do."}
        </span>
      </div>

      <div className="health-summary" aria-label="Tóm tắt kiểm tra chất lượng">
        <div><strong>{health.report.blocking_count}</strong><span>Lỗi chặn</span></div>
        <div><strong>{health.report.warning_count}</strong><span>Cảnh báo</span></div>
        <div><strong>{health.report.info_count}</strong><span>Thông tin</span></div>
        <div><strong>{String(health.standardized_eda.eligible_orders_count ?? 0)}</strong><span>Khoản thu hợp lệ</span></div>
        <div><strong>{String(health.standardized_eda.eligible_credit_count ?? 0)}</strong><span>Giao dịch ghi có</span></div>
      </div>

      <article className="surface issue-panel">
        <div className="surface-heading compact">
          <div><div><h2>Vấn đề cần xem xét</h2><p>Ưu tiên theo mức ảnh hưởng đến tính đúng đắn.</p></div></div>
          <span className="count-pill">{issues.length} vấn đề</span>
        </div>
        {issues.length === 0 ? (
          <p className="empty-state">Không phát hiện vấn đề chất lượng dữ liệu.</p>
        ) : (
          <div className="issue-list">
            {issues.map((issue, index) => {
              const key = issueKey(issue, index);
              const isEditing = editingKey === key;
              return (
                <article className="issue" key={key}>
                  <span className={`severity severity-${issue.severity.toLowerCase()}`}>{severityLabels[issue.severity]}</span>
                  <div className="issue-content">
                    <strong>{issue.message_vi}</strong>
                    {issue.source_rows.length > 0 && <p>Dòng nguồn: {issue.source_rows.join(", ")}</p>}
                    <details>
                      <summary>Chi tiết kỹ thuật</summary>
                      <code>{issue.code}</code> · feed <code>{issue.feed}</code>
                      {issue.sample_values.length > 0 && <p>Giá trị mẫu: {issue.sample_values.join(", ")}</p>}
                    </details>
                    {issue.severity === "BLOCKING" && issue.source_rows.length > 0 && !isEditing && (
                      <button className="text-button issue-action" type="button" disabled={busy} onClick={() => { setEditingKey(key); setReason(""); }}>
                        Loại trừ các dòng này
                      </button>
                    )}
                    {isEditing && (
                      <div className="exclusion-form">
                        <label htmlFor={`reason-${index}`}>Lý do loại trừ <span aria-hidden="true">*</span></label>
                        <textarea
                          id={`reason-${index}`}
                          value={reason}
                          onChange={(event) => setReason(event.target.value)}
                          placeholder="Mô tả lý do nghiệp vụ, tối thiểu 3 ký tự"
                          rows={2}
                        />
                        <div className="button-row">
                          <button className="secondary small" type="button" onClick={() => setEditingKey(null)}>Hủy</button>
                          <button className="primary small" type="button" disabled={busy || reason.trim().length < 3} onClick={() => onExclude(issue, reason.trim())}>
                            Xác nhận loại trừ
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </article>

      <div className="action-bar">
        <div>
          <strong>Quyết định kiểm soát</strong>
          <p>Cảnh báo và proposal không được tính vào KPI đã xác nhận.</p>
        </div>
        <div className="button-row">
          <button className="secondary" type="button" onClick={onBack} disabled={busy}>Quay lại ánh xạ</button>
          {health.report.warning_count > 0 && (
            <button className="secondary" type="button" disabled={busy || warningsAcknowledged} onClick={onAcknowledge}>
              {warningsAcknowledged ? "Đã ghi nhận cảnh báo" : "Ghi nhận cảnh báo"}
            </button>
          )}
          <button className="primary" type="button" disabled={busy || !ready} onClick={onRun}>
            {busy ? <><span className="spinner" aria-hidden="true" />Engine đang chạy…</> : "Chạy đối soát"}
          </button>
        </div>
      </div>
    </section>
  );
}
