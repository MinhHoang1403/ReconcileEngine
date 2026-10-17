import type { Inspection, MappingState } from "../types";

function StructureCard({ title, structure }: { title: string; structure: Inspection["detected_structure"]["orders"] }) {
  return <div className={structure.status === "NEEDS_REVIEW" ? "structure-card review" : "structure-card"}>
    <strong>{title}</strong>
    <span>{structure.selected.sheet_name ? `Sheet ${structure.selected.sheet_name}` : "File CSV"} · tiêu đề dòng {structure.selected.header_row_number}{structure.selected.header_depth > 1 ? ` (${structure.selected.header_depth} dòng)` : ""}</span>
    <small>{structure.status === "AUTO_SELECTED" ? "Đã xác định tự động" : "Cần bạn xác nhận cấu trúc"}</small>
    {structure.status === "NEEDS_REVIEW" && <ul>{structure.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}
  </div>;
}

export function ImportSummary({ inspection, mapping, onChange }: { inspection: Inspection; mapping: MappingState; onChange: (mapping: MappingState) => void }) {
  const analyses = Object.values(inspection.mapping_suggestions);
  const total = analyses.reduce((sum, item) => sum + item.required_total, 0);
  const ready = analyses.reduce((sum, item) => sum + item.required_auto_selected, 0);
  const review = analyses.reduce((sum, item) => sum + item.required_needs_review + item.required_unsupported, 0);
  const structureNeedsReview = Object.values(inspection.detected_structure).some((item) => item.status === "NEEDS_REVIEW");
  return <article className="surface import-summary">
    <div className="import-summary-heading"><div><span className="success-mark">✓</span><div><p className="eyebrow">PHÂN TÍCH HOÀN TẤT</p><h2>Đã phân tích và chuẩn bị dữ liệu</h2></div></div><span className={review ? "summary-chip attention" : "summary-chip"}>{review ? `${review} trường cần xác nhận` : `Đã xác định ${ready}/${total} trường bắt buộc`}</span></div>
    <div className="recognized-grid">
      <div><small>Loại nguồn đơn hàng</small><strong>{inspection.import_profile.recognized.orders.name}</strong><span>{inspection.import_profile.recognized.orders.status === "RECOGNIZED" ? "Đã nhận diện" : "Cần kiểm tra"}</span></div>
      <div><small>Loại nguồn thanh toán</small><strong>{inspection.import_profile.recognized.bank_transactions.name}</strong><span>{inspection.import_profile.recognized.bank_transactions.status === "RECOGNIZED" ? "Đã nhận diện" : "Cần kiểm tra"}</span></div>
      <div><small>Cấu hình đã lưu</small><strong>{inspection.import_profile.applied ? inspection.import_profile.saved_profile?.name : "Chưa áp dụng"}</strong><span>{inspection.import_profile.applied ? "Khớp chính xác cấu trúc file" : "Dùng đề xuất từ dữ liệu hiện tại"}</span></div>
    </div>
    <div className="structure-grid"><StructureCard title="Nguồn đơn hàng" structure={inspection.detected_structure.orders} /><StructureCard title="Nguồn giao dịch" structure={inspection.detected_structure.bank_transactions} /></div>
    {structureNeedsReview && <label className="structure-confirm"><input type="checkbox" checked={mapping.confirmed_structure} onChange={(event) => onChange({ ...mapping, confirmed_structure: event.target.checked })} /><span><strong>Tôi đã kiểm tra sheet và dòng tiêu đề ở trên</strong><small>Cần xác nhận trước khi chuẩn hóa vì file có nhiều cách diễn giải hợp lý.</small></span></label>}
  </article>;
}
