import { DetailDrawer } from "./DetailDrawer";
import type { DetailBankTransaction, DetailOrder, TransactionDetail } from "../types";

const relationshipLabels: Record<string, string> = {
  ONE_TO_ONE: "Một đơn hàng – một giao dịch",
  MANY_ORDERS_ONE_BANK: "Nhiều đơn hàng – một giao dịch",
  ONE_ORDER_MANY_BANKS: "Một đơn hàng – nhiều giao dịch",
  MANY_TO_MANY: "Nhiều đơn hàng – nhiều giao dịch",
};

const linkLabels: Record<string, string> = {
  CONFIRMED: "Đã xác nhận",
  PROPOSED: "Đề xuất, chưa xác nhận",
  UNMATCHED: "Chưa tìm thấy đối ứng",
};

const reasonLabels: Record<string, string> = {
  ORPHAN_BANK: "Chưa tìm thấy đơn hàng tương ứng",
  ORPHAN_INTERNAL: "Chưa tìm thấy giao dịch thanh toán tương ứng",
  NO_CONFIRMED_RECEIPT: "Chưa có khoản thu được xác nhận",
  PARTIAL_PAYMENT: "Thanh toán chưa đủ",
  OVERPAYMENT: "Có tiền nhận chưa phân bổ",
  AMBIGUOUS_MATCH: "Có nhiều phương án đối chiếu",
  FUZZY_REFERENCE: "Tham chiếu gần giống, cần kiểm tra",
};

function formatMoney(value: unknown, currency: string): string {
  const numeric = typeof value === "number" ? value : Number(value ?? 0);
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "BRL" ? 2 : 0,
  }).format(numeric / (currency === "BRL" ? 100 : 1));
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.join(", ") || "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function SourceBlock({ record }: { record: DetailOrder | DetailBankTransaction }) {
  return (
    <div className="source-trace">
      <p>
        Nguồn: <strong>{record.source.filename ?? "Không rõ tệp"}</strong>
        {record.source.sheet_name ? ` · trang tính ${record.source.sheet_name}` : ""}
        {record.source.row_number ? ` · dòng ${record.source.row_number}` : ""}
      </p>
      <details>
        <summary>Xem giá trị gốc và mã kiểm tra dòng</summary>
        <dl className="raw-value-grid">
          {Object.entries(record.source.raw_values).map(([key, value]) => (
            <div key={key}><dt>{key}</dt><dd>{displayValue(value)}</dd></div>
          ))}
        </dl>
        <p className="technical-id">Mã kiểm tra dòng: {record.source.row_hash ?? "—"}</p>
      </details>
    </div>
  );
}

function OrderCard({ record, currency }: { record: DetailOrder; currency: string }) {
  return (
    <article className="drawer-section">
      <h3>Đơn hàng {record.order_id}</h3>
      <dl className="record-grid">
        <div><dt>Ngày phát sinh</dt><dd>{displayValue(record.ordered_at)}</dd></div>
        <div><dt>Số tiền cần thu</dt><dd>{formatMoney(record.expected_amount_minor, currency)}</dd></div>
        <div><dt>Khách hàng</dt><dd>{displayValue(record.customer_name ?? record.customer_id)}</dd></div>
        <div><dt>Mã tham chiếu</dt><dd>{displayValue(record.external_ref)}</dd></div>
      </dl>
      <SourceBlock record={record} />
    </article>
  );
}

function BankCard({ record, currency }: { record: DetailBankTransaction; currency: string }) {
  return (
    <article className="drawer-section">
      <h3>Giao dịch thanh toán {record.bank_txn_id}</h3>
      <dl className="record-grid">
        <div><dt>Ngày giao dịch</dt><dd>{displayValue(record.txn_date)}</dd></div>
        <div><dt>Số tiền đã ghi nhận</dt><dd>{formatMoney(record.posted_amount_minor, currency)}</dd></div>
        <div><dt>Người chuyển</dt><dd>{displayValue(record.sender_name)}</dd></div>
        <div><dt>Nội dung / tham chiếu</dt><dd>{displayValue(record.description ?? record.txn_ref)}</dd></div>
      </dl>
      <SourceBlock record={record} />
    </article>
  );
}

export function TransactionDetailDrawer({ detail, currency, onClose }: {
  detail: TransactionDetail;
  currency: string;
  onClose: () => void;
}) {
  const relationship = detail.overview.relationship_types.map((value) => relationshipLabels[value] ?? value).join(", ");
  return (
    <DetailDrawer
      title="Chi tiết đối chiếu"
      subtitle={`${detail.entity_id} · ${linkLabels[detail.overview.link_status] ?? detail.overview.link_status}`}
      onClose={onClose}
    >
      <p className="detail-guidance">{detail.guidance_vi}</p>
      <section className="detail-summary-grid" aria-label="Tổng hợp số tiền">
        <div><span>Quan hệ đối chiếu</span><strong>{relationship || "Chưa có quan hệ"}</strong></div>
        <div><span>Tiền cần thu</span><strong>{formatMoney(detail.overview.expected_amount_minor, currency)}</strong></div>
        <div><span>Tiền đã ghi nhận</span><strong>{formatMoney(detail.overview.posted_amount_minor, currency)}</strong></div>
        <div><span>Tiền đã phân bổ</span><strong>{formatMoney(detail.overview.allocated_cash_minor, currency)}</strong></div>
        <div><span>Điều chỉnh đã xác minh</span><strong>{formatMoney(detail.overview.verified_adjustment_minor, currency)}</strong></div>
        <div><span>Còn phải thu</span><strong>{formatMoney(detail.overview.outstanding_minor, currency)}</strong></div>
        <div><span>Tiền nhận chưa phân bổ</span><strong>{formatMoney(detail.overview.unapplied_minor, currency)}</strong></div>
      </section>

      <div className="counterpart-grid">
        <div>{detail.orders.map((record) => <OrderCard key={record.order_id} record={record} currency={currency} />)}</div>
        <div>{detail.bank_transactions.map((record) => <BankCard key={record.bank_txn_id} record={record} currency={currency} />)}</div>
      </div>

      <section className="drawer-section">
        <h3>Phân bổ tiền đã xác nhận</h3>
        {detail.allocations.length === 0 ? (
          <p>Chưa có khoản phân bổ. Đề xuất đối chiếu không được tính vào số tiền đã xác nhận.</p>
        ) : (
          <div className="table-wrap"><table><thead><tr><th>Đơn hàng</th><th>Giao dịch</th><th>Số tiền phân bổ</th></tr></thead><tbody>
            {detail.allocations.map((edge) => <tr key={edge.edge_id}><td>{edge.order_id}</td><td>{edge.bank_txn_id}</td><td>{formatMoney(edge.allocated_cash_minor, currency)}</td></tr>)}
          </tbody></table></div>
        )}
      </section>

      {detail.adjustments.length > 0 && <section className="drawer-section"><h3>Điều chỉnh đã xác minh</h3>{detail.adjustments.map((item, index) => <p key={String(item.adjustment_id ?? index)}>{displayValue(item.adjustment_type)}: {formatMoney(item.amount_minor, currency)} · Bằng chứng: {displayValue(item.evidence_reference)}</p>)}</section>}

      <section className="drawer-section">
        <h3>Bằng chứng và lý do</h3>
        {detail.groups.map((group) => <div className="evidence-item" key={group.group_id}><strong>{group.evidence.explanation_vi}</strong><p>Quy tắc: {group.evidence.rule_id}</p>{group.evidence.reason_codes.length > 0 && <p>{group.evidence.reason_codes.map((code) => reasonLabels[code] ?? code).join(" · ")}</p>}</div>)}
        {detail.exceptions.map((item) => <div className="evidence-item" key={item.exception_id}><strong>{item.reason_codes.map((code) => reasonLabels[code] ?? code).join(" · ")}</strong><p>Giá trị cần kiểm tra: {formatMoney(item.risk_amount_minor, currency)}</p></div>)}
        {detail.groups.length === 0 && detail.exceptions.length === 0 && <p>Chưa có bằng chứng đủ mạnh để tạo quan hệ đối chiếu.</p>}
        <details><summary>Xem thông tin kỹ thuật</summary><pre>{JSON.stringify({ groups: detail.groups, candidates: detail.candidates, exceptions: detail.exceptions }, null, 2)}</pre></details>
      </section>
    </DetailDrawer>
  );
}
