import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { MappingState, NormalizedPreview as PreviewData } from "../types";

function PreviewTable({ title, rows }: { title: string; rows: Record<string, unknown>[] }) {
  const columns = rows.length ? Object.keys(rows[0]).filter((column) => column !== "lineage").slice(0, 7) : [];
  return (
    <article className="surface normalized-card">
      <div className="data-card__header"><div><span className="overline">SAU CHUẨN HÓA</span><h2>{title}</h2></div><span>{rows.length} dòng mẫu</span></div>
      {rows.length ? <div className="table-wrap preview-table"><table>
        <thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => <tr key={index}>{columns.map((column) => <td key={column}>{typeof row[column] === "object" ? JSON.stringify(row[column]) : String(row[column] ?? "")}</td>)}</tr>)}</tbody>
      </table></div> : <p className="empty-state">Chưa có dòng nào chuẩn hóa thành công trong phần xem trước.</p>}
    </article>
  );
}

export function NormalizedPreview({ sessionId, mapping, enabled }: { sessionId: string; mapping: MappingState; enabled: boolean }) {
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) {
      setPreview(null);
      return;
    }
    let current = true;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      api.previewMapping(sessionId, mapping)
        .then((value) => { if (current) setPreview(value); })
        .catch((caught) => { if (current) setError(caught instanceof Error ? caught.message : "Không thể tạo xem trước"); })
        .finally(() => { if (current) setLoading(false); });
    }, 350);
    return () => {
      current = false;
      window.clearTimeout(timer);
    };
  }, [enabled, mapping, sessionId]);

  return <section className="stack normalized-preview" aria-live="polite">
    <div className="preview-status">
      <div><h2>Xem trước dữ liệu sau chuẩn hóa</h2><p>Mỗi thay đổi cách ghép cột sẽ cập nhật lại phần này. Đây chưa phải thao tác đối soát.</p></div>
      {loading ? <span><span className="spinner" />Đang cập nhật…</span> : preview && <span className={preview.status === "READY" ? "ready" : "blocked"}>{preview.status === "READY" ? "Sẵn sàng" : `${preview.blocking_count} vấn đề phải sửa`}</span>}
    </div>
    {error && <div className="inline-error">{error}</div>}
    {preview && <>
      {preview.issues.filter((issue) => issue.severity === "BLOCKING").length > 0 && <div className="mapping-warning">{preview.issues.filter((issue) => issue.severity === "BLOCKING").slice(0, 3).map((issue) => <p key={`${issue.code}-${issue.source_rows.join("-")}`}>{issue.message_vi}</p>)}</div>}
      <div className="preview-grid"><PreviewTable title="Đơn hàng" rows={preview.orders} /><PreviewTable title="Giao dịch thanh toán" rows={preview.bank_transactions} /></div>
    </>}
  </section>;
}
