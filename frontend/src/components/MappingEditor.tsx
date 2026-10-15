import type { MappingState, RawEda } from "../types";

type FieldDefinition = { key: string; label: string; required?: boolean };

const orderFields: FieldDefinition[] = [
  { key: "order_id", label: "Mã khoản phải thu", required: true },
  { key: "ordered_at", label: "Ngày phát sinh", required: true },
  { key: "expected_amount", label: "Số tiền phải thu", required: true },
  { key: "currency", label: "Loại tiền" },
  { key: "order_status", label: "Trạng thái khoản thu" },
  { key: "external_ref", label: "Mã tham chiếu ngoài" },
  { key: "customer_name", label: "Tên khách hàng" },
  { key: "payment_channel", label: "Kênh thanh toán" },
  { key: "description", label: "Diễn giải" },
];

const bankFields: FieldDefinition[] = [
  { key: "bank_txn_id", label: "Mã giao dịch", required: true },
  { key: "txn_date", label: "Ngày giao dịch", required: true },
  { key: "posted_amount", label: "Số tiền hạch toán", required: true },
  { key: "direction", label: "Chiều giao dịch", required: true },
  { key: "amount_basis", label: "Cơ sở số tiền", required: true },
  { key: "txn_ref", label: "Mã tham chiếu" },
  { key: "value_date", label: "Ngày giá trị" },
  { key: "currency", label: "Loại tiền" },
  { key: "description", label: "Diễn giải" },
  { key: "sender_name", label: "Người chuyển" },
  { key: "channel", label: "Kênh giao dịch" },
  { key: "batch_ref", label: "Mã lô" },
  { key: "declared_fee", label: "Phí khai báo" },
];

type Props = {
  mapping: MappingState;
  ordersEda: RawEda;
  bankEda: RawEda;
  onChange: (mapping: MappingState) => void;
};

function Fields({ fields, columns, values, onField }: {
  fields: FieldDefinition[];
  columns: string[];
  values: Record<string, string>;
  onField: (field: string, source: string) => void;
}) {
  return (
    <div className="mapping-grid">
      {fields.map((field) => (
        <label key={field.key}>
          <span className="field-label">
            <span>{field.label}<small>{field.key}</small></span>
            {field.required && <em>Bắt buộc</em>}
          </span>
          <select
            required={field.required}
            value={values[field.key] ?? ""}
            onChange={(event) => onField(field.key, event.target.value)}
          >
            <option value="">— Không ánh xạ —</option>
            {columns.map((column) => <option key={column} value={column}>{column}</option>)}
          </select>
        </label>
      ))}
    </div>
  );
}

function FeedMapping({ title, description, fields, columns, values, onField }: {
  title: string;
  description: string;
  fields: FieldDefinition[];
  columns: string[];
  values: Record<string, string>;
  onField: (field: string, source: string) => void;
}) {
  const required = fields.filter((field) => field.required);
  const optional = fields.filter((field) => !field.required);
  return (
    <article className="surface mapping-card">
      <div className="surface-heading compact"><div><div><h2>{title}</h2><p>{description}</p></div></div></div>
      <h3 className="mapping-subtitle">Trường bắt buộc</h3>
      <Fields fields={required} columns={columns} values={values} onField={onField} />
      <details className="optional-fields">
        <summary>Trường bổ sung ({optional.length})</summary>
        <Fields fields={optional} columns={columns} values={values} onField={onField} />
      </details>
    </article>
  );
}

export function MappingEditor({ mapping, ordersEda, bankEda, onChange }: Props) {
  return (
    <div className="stack">
      <article className="surface mapping-settings">
        <div className="surface-heading compact"><div><div><h2>Cấu hình chuẩn hóa</h2><p>Thiết lập cách diễn giải tiền, nguồn và ngày tháng.</p></div></div></div>
        <div className="settings-row">
          <label>
            <span>Loại tiền</span>
            <select value={mapping.currency} onChange={(event) => onChange({ ...mapping, currency: event.target.value as "VND" | "BRL" })}>
              <option value="VND">VND — không có chữ số thập phân</option>
              <option value="BRL">BRL — 2 chữ số thập phân</option>
            </select>
          </label>
          <label>
            <span>Hồ sơ nguồn tiền</span>
            <select value={mapping.source_profile} onChange={(event) => onChange({ ...mapping, source_profile: event.target.value })}>
              <option value="BANK_CREDIT">Ngân hàng — giao dịch ghi có</option>
              <option value="PSP_NET_SETTLEMENT">PSP — quyết toán ròng</option>
            </select>
          </label>
          <label>
            <span>Định dạng ngày</span>
            <input value={mapping.date_format} onChange={(event) => onChange({ ...mapping, date_format: event.target.value })} />
          </label>
        </div>
      </article>
      <div className="mapping-columns">
        <FeedMapping
          title="Khoản phải thu"
          description={`${ordersEda.column_count} cột nguồn · ${ordersEda.row_count} dòng`}
          fields={orderFields}
          columns={ordersEda.columns}
          values={mapping.order_columns}
          onField={(field, source) => onChange({ ...mapping, order_columns: { ...mapping.order_columns, [field]: source } })}
        />
        <FeedMapping
          title="Ngân hàng / PSP"
          description={`${bankEda.column_count} cột nguồn · ${bankEda.row_count} dòng`}
          fields={bankFields}
          columns={bankEda.columns}
          values={mapping.bank_columns}
          onField={(field, source) => onChange({ ...mapping, bank_columns: { ...mapping.bank_columns, [field]: source } })}
        />
      </div>
    </div>
  );
}
