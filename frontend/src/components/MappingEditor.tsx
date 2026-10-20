import { useEffect, useMemo } from "react";
import type { MappingAnalysis, MappingState, MappingSuggestion, RawEda } from "../types";

type FieldDefinition = { key: string; label: string; description: string; required?: boolean; usage?: string };

const orderFields: FieldDefinition[] = [
  { key: "order_id", label: "Mã đơn hàng", description: "Mã duy nhất để nhận diện khoản tiền cần thu; giữ nguyên số 0 ở đầu.", required: true },
  { key: "ordered_at", label: "Ngày phát sinh đơn hàng", description: "Dùng để kiểm tra khoảng thời gian thanh toán.", required: true },
  { key: "expected_amount", label: "Số tiền cần thu", description: "Số tiền hệ thống cần đối chiếu cho đơn hàng.", required: true },
  { key: "currency", label: "Loại tiền", description: "Nếu không có cột, hệ thống dùng loại tiền đã chọn cho cả phiên.", usage: "Kiểm tra dữ liệu" },
  { key: "order_status", label: "Trạng thái đơn hàng", description: "Xác định đơn hàng có đủ điều kiện đối soát hay không.", usage: "Cốt lõi" },
  { key: "external_ref", label: "Mã tham chiếu thanh toán", description: "Bằng chứng mạnh khi mã này xuất hiện trong giao dịch thanh toán.", usage: "Cốt lõi" },
  { key: "customer_name", label: "Tên khách hàng", description: "Chỉ hỗ trợ tìm ứng viên; không tự xác nhận giao dịch.", usage: "Hỗ trợ" },
  { key: "payment_channel", label: "Kênh thanh toán", description: "Hỗ trợ kiểm tra tính tương thích của nguồn tiền.", usage: "Hỗ trợ" },
  { key: "description", label: "Diễn giải", description: "Dùng làm bằng chứng bổ sung và hiển thị khi truy vết.", usage: "Hỗ trợ" },
];

const bankFields: FieldDefinition[] = [
  { key: "bank_txn_id", label: "Mã giao dịch thanh toán", description: "Mã duy nhất của dòng tiền; giúp ngăn phân bổ trùng.", required: true },
  { key: "txn_date", label: "Ngày giao dịch", description: "Ngày ghi nhận giao dịch theo nguồn thanh toán.", required: true },
  { key: "posted_amount", label: "Số tiền thực nhận", description: "Tiền thực tế đã ghi có hoặc số tiền quyết toán ròng.", required: true },
  { key: "direction", label: "Chiều giao dịch", description: "Phân biệt tiền vào (CREDIT) và tiền ra (DEBIT).", required: true },
  { key: "amount_basis", label: "Cơ sở số tiền", description: "Xác nhận đây là tiền đã ghi có, quyết toán ròng hay số tổng trước phí.", required: true },
  { key: "txn_ref", label: "Mã tham chiếu", description: "Mã ngân hàng hoặc cổng thanh toán cung cấp.", usage: "Cốt lõi" },
  { key: "value_date", label: "Ngày hiệu lực", description: "Ngày tiền có hiệu lực nếu nguồn có cung cấp.", usage: "Hỗ trợ" },
  { key: "currency", label: "Loại tiền", description: "Nếu không có cột, dùng loại tiền đã chọn cho cả phiên.", usage: "Kiểm tra dữ liệu" },
  { key: "description", label: "Nội dung giao dịch", description: "Có thể chứa mã đơn hàng và bằng chứng ghép.", usage: "Cốt lõi" },
  { key: "sender_name", label: "Người chuyển", description: "Chỉ hỗ trợ xếp hạng ứng viên; không tự xác nhận.", usage: "Hỗ trợ" },
  { key: "channel", label: "Kênh giao dịch", description: "Ngân hàng, chuyển khoản hoặc cổng thanh toán.", usage: "Hỗ trợ" },
  { key: "batch_ref", label: "Mã đợt quyết toán", description: "Hữu ích cho giao dịch gộp từ cổng thanh toán.", usage: "Cốt lõi khi có" },
  { key: "declared_fee", label: "Phí được nguồn khai báo", description: "Chỉ dùng khi có chính sách phí hợp lệ; không tự suy đoán từ chênh lệch.", usage: "Cốt lõi khi có" },
];

type Props = {
  mapping: MappingState;
  ordersEda: RawEda;
  bankEda: RawEda;
  onChange: (mapping: MappingState) => void;
  onValidityChange?: (valid: boolean) => void;
  suggestions: { orders: MappingAnalysis; bank_transactions: MappingAnalysis };
  compact?: boolean;
  showParsing?: boolean;
};

function mappingProblems(fields: FieldDefinition[], values: Record<string, string>, transformations: MappingState["bank_transformations"] = {}) {
  const cashTransformation = transformations.cash_movement;
  const covered = cashTransformation ? new Set(["posted_amount", "direction"]) : new Set<string>();
  const missing = fields.filter((field) => field.required && !values[field.key] && !covered.has(field.key));
  const selected = new Map<string, string[]>();
  Object.entries(values).forEach(([field, source]) => {
    if (source) selected.set(source, [...(selected.get(source) ?? []), field]);
  });
  const reused = [...selected.entries()].filter(([, mappedFields]) => mappedFields.length > 1);
  return { missing, reused };
}

function Fields({ fields, columns, values, sampleRows, onField, suggestions, transformations, onManualCash }: {
  fields: FieldDefinition[];
  columns: string[];
  values: Record<string, string>;
  sampleRows: Record<string, unknown>[];
  onField: (field: string, source: string) => void;
  suggestions?: MappingSuggestion[];
  transformations?: MappingState["bank_transformations"];
  onManualCash?: () => void;
}) {
  return (
    <div className="mapping-grid">
      {fields.map((field) => {
        const selectedColumn = values[field.key] ?? "";
        const samples = selectedColumn
          ? sampleRows.map((row) => row[selectedColumn]).filter((value) => value !== "" && value != null).slice(0, 3)
          : [];
        const suggestion = suggestions?.find((item) => item.canonical_target === field.key);
        const derived = ["posted_amount", "direction"].includes(field.key) && transformations?.cash_movement;
        return <label key={field.key} className={suggestion?.status === "needs-review" || suggestion?.status === "unsupported" ? "needs-review" : ""}>
          <span className="field-label">
            <span>{field.label}</span>
            {field.required ? <em>Bắt buộc</em> : <em className="optional-tag">{field.usage}</em>}
          </span>
          <span className="field-help">{field.description}</span>
          {derived ? <div className="transformation-choice">
            <strong>Tự dựng từ cột ghi có / ghi nợ</strong>
            <span>{String(transformations?.cash_movement.credit_column)} · {String(transformations?.cash_movement.debit_column)}</span>
            <button type="button" className="text-button" onClick={onManualCash}>Ghép cột thủ công</button>
          </div> : <select
            required={field.required}
            value={values[field.key] ?? ""}
            onChange={(event) => onField(field.key, event.target.value)}
          >
            <option value="">— Chưa ghép cột —</option>
            {columns.map((column) => <option key={column} value={column}>{column}</option>)}
          </select>}
          {field.required && !selectedColumn && !derived && <span className="field-error">Cần chọn cột nguồn để chuẩn hóa trường này.</span>}
          {selectedColumn && <span className="field-sample">Giá trị mẫu: {samples.length ? samples.map(String).join(" · ") : "không có giá trị trong phần xem trước"}</span>}
          {suggestion && <details className={`mapping-evidence status-${suggestion.status}`} open={suggestion.status !== "auto-selected"}>
            <summary>{suggestion.status === "auto-selected" ? "Đã gợi ý" : suggestion.status === "unsupported" ? "Chưa xác định được" : "Cần xác nhận"} · Tin cậy {suggestion.confidence === "HIGH" ? "cao" : suggestion.confidence === "MEDIUM" ? "trung bình" : "thấp"}</summary>
            <ul>{suggestion.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
          </details>}
        </label>;
      })}
    </div>
  );
}

function FeedMapping({ title, description, fields, columns, values, sampleRows, onField, suggestions, transformations, onManualCash, compact }: {
  title: string;
  description: string;
  fields: FieldDefinition[];
  columns: string[];
  values: Record<string, string>;
  sampleRows: Record<string, unknown>[];
  onField: (field: string, source: string) => void;
  suggestions: MappingSuggestion[];
  transformations?: MappingState["bank_transformations"];
  onManualCash?: () => void;
  compact?: boolean;
}) {
  const required = fields.filter((field) => field.required);
  const optional = fields.filter((field) => !field.required);
  const problems = mappingProblems(fields, values, transformations);
  const unresolved = required.filter((field) => suggestions.find((item) => item.canonical_target === field.key)?.status !== "auto-selected"
    || (!values[field.key] && !(["posted_amount", "direction"].includes(field.key) && transformations?.cash_movement)));
  const known = required.filter((field) => !unresolved.includes(field));
  return (
    <article className="surface mapping-card">
      <div className="surface-heading compact"><div><div><h2>{title}</h2><p>{description}</p></div></div></div>
      {problems.reused.length > 0 && (
        <div className="mapping-warning" role="alert">
          Một cột nguồn đang được dùng cho nhiều trường: {problems.reused.map(([source, mapped]) => `${source} (${mapped.join(", ")})`).join("; ")}. Hãy chọn mỗi cột đúng một lần.
        </div>
      )}
      <h3 className="mapping-subtitle">Trường bắt buộc</h3>
      {compact && <p className="optional-note">{known.length} trường đã được nhận diện. Chỉ cần xác nhận các mục còn lại.</p>}
      <Fields fields={compact ? unresolved : required} columns={columns} values={values} sampleRows={sampleRows} onField={onField} suggestions={suggestions} transformations={transformations} onManualCash={onManualCash} />
      {compact && known.length > 0 && <details className="optional-fields"><summary>Xem hoặc sửa các trường đã nhận diện ({known.length})</summary>
        <Fields fields={known} columns={columns} values={values} sampleRows={sampleRows} onField={onField} suggestions={suggestions} transformations={transformations} onManualCash={onManualCash} />
      </details>}
      <details className="optional-fields">
        <summary>Trường bổ sung ({optional.length})</summary>
        <p className="optional-note">Các trường bổ sung làm rõ bằng chứng hoặc phục vụ hiển thị. Trường ghi “Hỗ trợ” không đủ để tự xác nhận giao dịch.</p>
        <Fields fields={optional} columns={columns} values={values} sampleRows={sampleRows} onField={onField} suggestions={suggestions} transformations={transformations} onManualCash={onManualCash} />
      </details>
    </article>
  );
}

export function MappingEditor({ mapping, ordersEda, bankEda, onChange, onValidityChange, suggestions, compact = false, showParsing = false }: Props) {
  const valid = useMemo(() => {
    const orderProblems = mappingProblems(orderFields, mapping.order_columns);
    const bankProblems = mappingProblems(bankFields, mapping.bank_columns, mapping.bank_transformations);
    return orderProblems.missing.length === 0 && bankProblems.missing.length === 0
      && orderProblems.reused.length === 0 && bankProblems.reused.length === 0;
  }, [mapping]);
  useEffect(() => onValidityChange?.(valid), [onValidityChange, valid]);
  return (
    <div className="stack">
      <details className="surface mapping-settings" open={!compact || showParsing}>
        <summary>Cách đọc tiền, ngày và loại tiền</summary>
        <div className="surface-heading compact"><div><div><h2>Cách đọc dữ liệu nguồn</h2><p>Thiết lập cách diễn giải tiền, nguồn và ngày tháng. Hệ thống không tự tạo mã, ngày hoặc số tiền còn thiếu.</p></div></div></div>
        <div className="settings-row">
          <label>
            <span>Loại tiền</span>
            <select value={mapping.currency} onChange={(event) => onChange({ ...mapping, currency: event.target.value as "VND" | "BRL" })}>
              <option value="VND">VND — không có chữ số thập phân</option>
              <option value="BRL">BRL — 2 chữ số thập phân</option>
            </select>
          </label>
          <label>
            <span>Loại nguồn giao dịch</span>
            <select value={mapping.source_profile} onChange={(event) => onChange({ ...mapping, source_profile: event.target.value })}>
              <option value="BANK_CREDIT">Ngân hàng — tiền thực tế ghi có</option>
              <option value="PSP_NET_SETTLEMENT">Cổng thanh toán (PSP) — tiền quyết toán ròng</option>
            </select>
          </label>
          <label>
            <span>Ngày trong file đơn hàng</span>
            <select value={mapping.order_date_format ?? "AUTO"} onChange={(event) => onChange({ ...mapping, order_date_format: event.target.value })}>
              <option value="AUTO">Tự nhận diện an toàn</option><option value="%Y-%m-%d">Năm-tháng-ngày</option><option value="%d/%m/%Y">Ngày/tháng/năm</option><option value="%m/%d/%Y">Tháng/ngày/năm</option>
            </select>
          </label>
          <label>
            <span>Ngày trong file giao dịch</span>
            <select value={mapping.bank_date_format ?? "AUTO"} onChange={(event) => onChange({ ...mapping, bank_date_format: event.target.value })}>
              <option value="AUTO">Tự nhận diện an toàn</option><option value="%Y-%m-%d">Năm-tháng-ngày</option><option value="%d/%m/%Y">Ngày/tháng/năm</option><option value="%m/%d/%Y">Tháng/ngày/năm</option>
            </select>
          </label>
        </div>
        <div className="settings-row">
          <label><span>Dấu thập phân</span><select value={mapping.decimal_separator} onChange={(event) => onChange({ ...mapping, decimal_separator: event.target.value, thousand_separator: mapping.thousand_separator === event.target.value ? null : mapping.thousand_separator })}>
            <option value=".">Dấu chấm (.)</option><option value=",">Dấu phẩy (,)</option>
          </select></label>
          <label><span>Dấu phân cách hàng nghìn</span><select value={mapping.thousand_separator ?? ""} onChange={(event) => onChange({ ...mapping, thousand_separator: event.target.value || null })}>
            <option value="">Không dùng</option><option value="," disabled={mapping.decimal_separator === ","}>Dấu phẩy (,)</option><option value="." disabled={mapping.decimal_separator === "."}>Dấu chấm (.)</option><option value=" ">Khoảng trắng</option>
          </select></label>
        </div>
        <div className="defaults-note"><strong>Giá trị mặc định được áp dụng rõ ràng</strong><span>Trạng thái đơn hàng: ELIGIBLE (đủ điều kiện đối soát). Loại tiền: {mapping.currency}. Không có mặc định giả cho mã, ngày, số tiền, chiều giao dịch hoặc cơ sở số tiền.</span></div>
      </details>
      <div className="mapping-columns">
        <FeedMapping
          title="Danh sách đơn hàng cần thu tiền"
          description={`${ordersEda.column_count} cột nguồn · ${ordersEda.row_count} dòng`}
          fields={orderFields}
          columns={ordersEda.columns}
          values={mapping.order_columns}
          sampleRows={ordersEda.sample_rows}
          suggestions={suggestions.orders.suggestions}
          compact={compact}
          onField={(field, source) => onChange({ ...mapping, order_columns: { ...mapping.order_columns, [field]: source } })}
        />
        <FeedMapping
          title="Danh sách giao dịch thanh toán"
          description={`${bankEda.column_count} cột nguồn · ${bankEda.row_count} dòng`}
          fields={bankFields}
          columns={bankEda.columns}
          values={mapping.bank_columns}
          sampleRows={bankEda.sample_rows}
          suggestions={suggestions.bank_transactions.suggestions}
          compact={compact}
          transformations={mapping.bank_transformations}
          onManualCash={() => {
            const next = { ...mapping.bank_transformations };
            delete next.cash_movement;
            onChange({ ...mapping, bank_transformations: next });
          }}
          onField={(field, source) => onChange({ ...mapping, bank_columns: { ...mapping.bank_columns, [field]: source } })}
        />
      </div>
    </div>
  );
}
