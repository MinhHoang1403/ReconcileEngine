import type { RawEda } from "../types";

export function RawPreview({ title, data }: { title: string; data: RawEda }) {
  const missingValues = Object.values(data.missing_by_column).reduce((total, value) => total + value, 0);
  const confidenceLabels: Record<string, string> = {
    HIGH: "Cao",
    MEDIUM: "Trung bình",
    LOW: "Thấp",
    PRELIMINARY_BEFORE_MAPPING: "Sơ bộ trước ánh xạ",
  };
  return (
    <article className="surface preview-card">
      <div className="data-card__header">
        <div><span className="overline">DỮ LIỆU THÔ</span><h2>{title}</h2></div>
        <span className="confidence-pill">Tin cậy: {confidenceLabels[data.confidence] ?? data.confidence}</span>
      </div>
      <div className="preview-stats" aria-label={`Thống kê ${title}`}>
        <span><strong>{data.row_count}</strong> dòng</span>
        <span><strong>{data.column_count}</strong> cột</span>
        <span><strong>{missingValues}</strong> ô trống</span>
        <span><strong>{data.duplicate_rows}</strong> dòng trùng</span>
      </div>
      <div className="table-wrap preview-table">
        <table>
          <caption className="sr-only">Năm dòng dữ liệu mẫu từ {title}</caption>
          <thead><tr>{data.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
          <tbody>
            {data.sample_rows.slice(0, 5).map((row, index) => (
              <tr key={index}>{data.columns.map((column) => <td key={column}>{String(row[column] ?? "")}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}
