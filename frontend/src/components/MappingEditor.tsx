import type { MappingState, RawEda } from "../types";

const orderFields = ["order_id", "ordered_at", "expected_amount", "currency", "order_status", "external_ref", "customer_name", "payment_channel", "description"];
const bankFields = ["bank_txn_id", "txn_ref", "txn_date", "value_date", "posted_amount", "direction", "amount_basis", "currency", "description", "sender_name", "channel", "batch_ref", "declared_fee"];

type Props = {
  mapping: MappingState;
  ordersEda: RawEda;
  bankEda: RawEda;
  onChange: (mapping: MappingState) => void;
};

function FeedMapping({
  title,
  fields,
  columns,
  values,
  onField,
}: {
  title: string;
  fields: string[];
  columns: string[];
  values: Record<string, string>;
  onField: (field: string, source: string) => void;
}) {
  return (
    <article className="data-card">
      <h3>{title}</h3>
      <div className="mapping-grid">
        {fields.map((field) => (
          <label key={field}>
            <span>{field}</span>
            <select value={values[field] ?? ""} onChange={(event) => onField(field, event.target.value)}>
              <option value="">— Không map —</option>
              {columns.map((column) => <option key={column} value={column}>{column}</option>)}
            </select>
          </label>
        ))}
      </div>
    </article>
  );
}

export function MappingEditor({ mapping, ordersEda, bankEda, onChange }: Props) {
  return (
    <div className="stack">
      <div className="settings-row">
        <label>
          Currency
          <select value={mapping.currency} onChange={(event) => onChange({ ...mapping, currency: event.target.value as "VND" | "BRL" })}>
            <option value="VND">VND — 0 minor digits</option>
            <option value="BRL">BRL — 2 minor digits</option>
          </select>
        </label>
        <label>
          Source profile
          <select value={mapping.source_profile} onChange={(event) => onChange({ ...mapping, source_profile: event.target.value })}>
            <option value="BANK_CREDIT">Bank credit</option>
            <option value="PSP_NET_SETTLEMENT">PSP net settlement</option>
          </select>
        </label>
        <label>
          Date format
          <input value={mapping.date_format} onChange={(event) => onChange({ ...mapping, date_format: event.target.value })} />
        </label>
      </div>
      <div className="two-column">
        <FeedMapping title="Khoản phải thu" fields={orderFields} columns={ordersEda.columns} values={mapping.order_columns} onField={(field, source) => onChange({ ...mapping, order_columns: { ...mapping.order_columns, [field]: source } })} />
        <FeedMapping title="Ngân hàng / PSP" fields={bankFields} columns={bankEda.columns} values={mapping.bank_columns} onField={(field, source) => onChange({ ...mapping, bank_columns: { ...mapping.bank_columns, [field]: source } })} />
      </div>
    </div>
  );
}

