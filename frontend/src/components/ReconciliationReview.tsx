import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../api/client";
import type { ReviewHistoryItem, ReviewPage, ReviewQueueItem } from "../types";
import { formatMoney } from "../utils/money";

const relationshipLabels: Record<string, string> = {
  ONE_TO_ONE: "Một đơn hàng - một giao dịch",
  MANY_ORDERS_ONE_BANK: "Nhiều đơn hàng - một giao dịch",
  ONE_ORDER_MANY_BANKS: "Một đơn hàng - nhiều giao dịch",
  AMBIGUOUS_CANDIDATES: "Nhiều phương án phức tạp",
};

const actionLabels: Record<string, string> = {
  APPROVE_GROUP: "Đã chấp thuận",
  REJECT_GROUP: "Đã từ chối",
  UNDO_ACTION: "Đã hoàn tác",
};

function emptyPage<T>(runId: string, revision: number): ReviewPage<T> {
  return { run_id: runId, effective_revision: revision, items: [], page: 1, page_size: 20, total: 0 };
}

function idempotencyKey(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") return globalThis.crypto.randomUUID();
  return `review-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function ReconciliationReview({
  runId,
  currency,
  effectiveRevision,
  onOpenGroup,
  onRevisionChanged,
}: {
  runId: string;
  currency: string;
  effectiveRevision: number;
  onOpenGroup: (groupId: string) => void | Promise<void>;
  onRevisionChanged: () => void | Promise<void>;
}) {
  const [queue, setQueue] = useState<ReviewPage<ReviewQueueItem>>(
    emptyPage(runId, effectiveRevision),
  );
  const [history, setHistory] = useState<ReviewPage<ReviewHistoryItem>>(
    emptyPage(runId, effectiveRevision),
  );
  const [queuePage, setQueuePage] = useState(1);
  const [historyPage, setHistoryPage] = useState(1);
  const [queryInput, setQueryInput] = useState("");
  const [query, setQuery] = useState("");
  const [groupType, setGroupType] = useState("");
  const [selected, setSelected] = useState<ReviewQueueItem | null>(null);
  const [actorLabel, setActorLabel] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const snapshotIsStale = queue.effective_revision !== effectiveRevision || history.effective_revision !== effectiveRevision;

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextQueue, nextHistory] = await Promise.all([
        api.reviews(runId, queuePage, 20, query, groupType),
        api.reviewHistory(runId, historyPage, 20),
      ]);
      setQueue(nextQueue);
      setHistory(nextHistory);
      setSelected((current) =>
        current ? nextQueue.items.find((item) => item.group_id === current.group_id) ?? null : null,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể tải danh sách cần xác minh");
    } finally {
      setLoading(false);
    }
  }, [groupType, historyPage, query, queuePage, runId]);

  useEffect(() => {
    void loadData();
  }, [loadData, effectiveRevision]);

  async function finishAction(operation: () => Promise<{ action_type: string; effective_revision: number }>) {
    setError(null);
    setMessage(null);
    try {
      const result = await operation();
      setMessage(`${actionLabels[result.action_type] ?? result.action_type}. Revision hiệu lực: ${result.effective_revision}.`);
      setSelected(null);
      setNote("");
      await onRevisionChanged();
      await loadData();
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "STALE_REVISION") {
        setError("Dữ liệu đã thay đổi ở nơi khác. Danh sách đang được tải lại trước khi bạn thao tác tiếp.");
        await loadData();
      } else {
        setError(caught instanceof Error ? caught.message : "Không thể ghi nhận quyết định");
      }
    } finally {
      setBusy(null);
    }
  }

  function approve() {
    if (!selected || !selected.can_approve || busy) return;
    setBusy("approve");
    void finishAction(() =>
      api.approveReview(runId, {
        group_id: selected.group_id,
        expected_revision: queue.effective_revision,
        idempotency_key: idempotencyKey(),
        actor_label: actorLabel.trim() || undefined,
        note: note.trim(),
      }),
    );
  }

  function reject() {
    if (!selected || note.trim().length === 0 || busy) return;
    setBusy("reject");
    void finishAction(() =>
      api.rejectReview(runId, {
        group_id: selected.group_id,
        expected_revision: queue.effective_revision,
        idempotency_key: idempotencyKey(),
        actor_label: actorLabel.trim() || undefined,
        note: note.trim(),
      }),
    );
  }

  function undo(action: ReviewHistoryItem) {
    if (busy) return;
    setBusy(action.action_id);
    void finishAction(() =>
      api.undoReview(runId, {
        action_id: action.action_id,
        expected_revision: history.effective_revision,
        idempotency_key: idempotencyKey(),
        actor_label: actorLabel.trim() || undefined,
        note: note.trim() || undefined,
      }),
    );
  }

  return (
    <section className="dashboard-section" aria-labelledby="review-title">
      <div className="section-label">
        <span>C</span>
        <div>
          <h2 id="review-title">Giao dịch cần xác minh</h2>
          <p>Kiểm tra bằng chứng và phép phân bổ trước khi chấp thuận. Mỗi quyết định tạo một revision và audit riêng.</p>
        </div>
      </div>
      <article className="surface review-workspace">
        <form
          className="review-tools"
          onSubmit={(event) => {
            event.preventDefault();
            setQueuePage(1);
            setQuery(queryInput.trim());
          }}
        >
          <label className="search-field">
            <span className="sr-only">Tìm đề xuất cần xác minh</span>
            <input value={queryInput} onChange={(event) => setQueryInput(event.target.value)} placeholder="Tìm mã đơn, giao dịch hoặc quy tắc" />
          </label>
          <label className="filter-field">
            <span className="sr-only">Lọc loại quan hệ cần xác minh</span>
            <select value={groupType} onChange={(event) => { setGroupType(event.target.value); setQueuePage(1); }}>
              <option value="">Tất cả loại quan hệ</option>
              <option value="ONE_TO_ONE">Một đơn - một giao dịch</option>
              <option value="MANY_ORDERS_ONE_BANK">Nhiều đơn - một giao dịch</option>
              <option value="ONE_ORDER_MANY_BANKS">Một đơn - nhiều giao dịch</option>
              <option value="AMBIGUOUS_CANDIDATES">Phương án phức tạp</option>
            </select>
          </label>
          <button className="secondary" type="submit">Tìm kiếm</button>
          <span className="loaded-count">Revision {queue.effective_revision} · {queue.total} đề xuất đang chờ</span>
        </form>

        {error && <div className="inline-error" role="alert">{error}</div>}
        {message && <div className="inline-success" role="status">{message}</div>}
        {snapshotIsStale && <div className="inline-warning" role="alert">Dashboard đang ở revision {effectiveRevision}, trong khi dữ liệu xác minh mới nhất là revision {Math.max(queue.effective_revision, history.effective_revision)}. <button className="text-button" type="button" onClick={() => void onRevisionChanged()}>Tải lại toàn bộ</button></div>}
        {loading ? <p className="empty-state">Đang tải danh sách xác minh...</p> : (
          <div className="table-wrap review-table">
            <table>
              <caption className="sr-only">Danh sách đề xuất cần xác minh</caption>
              <thead><tr><th>Quan hệ</th><th>Đơn hàng</th><th>Giao dịch</th><th>Tiền đề xuất</th><th>Phương pháp</th><th>Trạng thái</th><th>Thao tác</th></tr></thead>
              <tbody>{queue.items.map((item) => (
                <tr key={item.group_id}>
                  <td>{relationshipLabels[item.group_type] ?? item.group_type}</td>
                  <td>{item.order_ids.join(", ")}</td>
                  <td>{item.bank_txn_ids.join(", ")}</td>
                  <td>{formatMoney(item.proposed_cash_minor, currency)}</td>
                  <td>{item.evidence.rule_id}</td>
                  <td><span className={`status-tag ${item.can_approve ? "status-proposed" : "status-blocked"}`}>{item.can_approve ? (item.review_status === "UNDONE" ? "Đã hoàn tác, chờ xác minh lại" : "Chờ xác minh") : "Không thể chấp thuận"}</span></td>
                  <td><button className="text-button" type="button" onClick={() => { setSelected(item); setNote(""); }}>Xem và xử lý</button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
        {!loading && queue.items.length === 0 && <p className="empty-state">Không có đề xuất phù hợp đang chờ xác minh.</p>}
        <div className="review-pagination">
          <button className="secondary" type="button" disabled={queuePage <= 1} onClick={() => setQueuePage((value) => value - 1)}>Trang trước</button>
          <span>Trang {queue.page}</span>
          <button className="secondary" type="button" disabled={queue.page * queue.page_size >= queue.total} onClick={() => setQueuePage((value) => value + 1)}>Trang sau</button>
        </div>

        {selected && (
          <section className="review-decision" aria-labelledby="review-decision-title">
            <div className="review-decision-heading">
              <div><h3 id="review-decision-title">Xác minh {selected.group_id}</h3><p>{selected.evidence.explanation_vi}</p></div>
              <button className="text-button" type="button" onClick={() => void onOpenGroup(selected.group_id)}>Xem dữ liệu nguồn và bằng chứng</button>
            </div>
            <div className="review-counterparts">
              <div><h4>Đơn hàng</h4>{selected.order_records.map((record) => <dl key={record.order_id}><div><dt>Mã</dt><dd>{record.order_id}</dd></div><div><dt>Ngày</dt><dd>{record.ordered_at}</dd></div><div><dt>Cần thu</dt><dd>{formatMoney(record.expected_amount_minor, currency)}</dd></div><div><dt>Tham chiếu</dt><dd>{record.external_ref || "-"}</dd></div></dl>)}</div>
              <div><h4>Giao dịch thanh toán</h4>{selected.bank_records.map((record) => <dl key={record.bank_txn_id}><div><dt>Mã</dt><dd>{record.bank_txn_id}</dd></div><div><dt>Ngày</dt><dd>{record.txn_date}</dd></div><div><dt>Đã ghi nhận</dt><dd>{formatMoney(record.posted_amount_minor, currency)}</dd></div><div><dt>Cơ sở tiền</dt><dd>{record.amount_basis}</dd></div></dl>)}</div>
            </div>
            <div className="allocation-preview">
              <h4>Phân bổ sẽ có hiệu lực nếu chấp thuận</h4>
              {selected.proposed_allocations.length > 0 ? selected.proposed_allocations.map((edge) => <p key={edge.edge_id}>{edge.order_id} ← {edge.bank_txn_id}: <strong>{formatMoney(edge.allocated_cash_minor, currency)}</strong></p>) : <p>Không có phân bổ an toàn để áp dụng.</p>}
              {selected.competing_candidate_ids.length > 0 && <p className="review-warning">Đề xuất cạnh tranh: {selected.competing_candidate_ids.join(", ")}</p>}
              {selected.conflict_message && <p className="review-warning">{selected.conflict_message}</p>}
            </div>
            <div className="review-form-grid">
              <label><span>Nhãn người thao tác (không phải danh tính đã xác thực)</span><input value={actorLabel} maxLength={120} onChange={(event) => setActorLabel(event.target.value)} placeholder="Ví dụ: kế toán ca sáng" /></label>
              <label><span>Ghi chú quyết định</span><textarea value={note} maxLength={2000} onChange={(event) => setNote(event.target.value)} placeholder="Bằng chứng đã kiểm tra hoặc lý do từ chối" /></label>
            </div>
            <div className="button-row">
              <button className="secondary danger" type="button" disabled={snapshotIsStale || Boolean(busy) || note.trim().length === 0} onClick={reject}>{busy === "reject" ? "Đang từ chối..." : "Từ chối đề xuất"}</button>
              <button className="primary" type="button" disabled={snapshotIsStale || Boolean(busy) || !selected.can_approve || note.trim().length === 0} onClick={approve}>{busy === "approve" ? "Đang chấp thuận..." : "Chấp thuận phân bổ"}</button>
            </div>
          </section>
        )}

        <section className="review-history" aria-labelledby="review-history-title">
          <div className="review-decision-heading"><div><h3 id="review-history-title">Lịch sử xác minh</h3><p>Nhãn người thao tác trong demo không phải danh tính đã xác thực.</p></div><span>{history.total} hành động</span></div>
          <div className="table-wrap"><table><thead><tr><th>Thời điểm</th><th>Quyết định</th><th>Nhóm</th><th>Revision</th><th>Tiền thay đổi</th><th>Ghi chú</th><th>Thao tác</th></tr></thead><tbody>{history.items.map((item) => <tr key={item.action_id}><td>{new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(new Date(item.created_at))}</td><td>{actionLabels[item.action_type]}</td><td>{item.target_group_id || "-"}</td><td>{item.revision_before} → {item.revision_after}</td><td>{formatMoney(item.allocation_delta_minor, currency)}</td><td>{item.note || "-"}</td><td>{item.action_type !== "UNDO_ACTION" && item.revision_after === history.effective_revision ? <button className="text-button" type="button" disabled={snapshotIsStale || Boolean(busy)} onClick={() => undo(item)}>{busy === item.action_id ? "Đang hoàn tác..." : "Hoàn tác"}</button> : "-"}</td></tr>)}</tbody></table></div>
          {history.items.length === 0 && <p className="empty-state">Chưa có quyết định xác minh nào.</p>}
          <div className="review-pagination"><button className="secondary" type="button" disabled={historyPage <= 1} onClick={() => setHistoryPage((value) => value - 1)}>Trang trước</button><span>Trang {history.page}</span><button className="secondary" type="button" disabled={history.page * history.page_size >= history.total} onClick={() => setHistoryPage((value) => value + 1)}>Trang sau</button></div>
        </section>
      </article>
    </section>
  );
}
