import type { RawEda } from "../types";

export function RawPreview({ title, data }: { title: string; data: RawEda }) {
  return (
    <article className="data-card">
      <div className="data-card__header">
        <div>
          <span className="overline">DỮ LIỆU THÔ</span>
          <h3>{title}</h3>
        </div>
        <span className="count-pill">{data.row_count} dòng</span>
      </div>
      <p className="muted">
        {data.column_count} cột · {data.duplicate_rows} dòng trùng hoàn toàn · thống kê sơ bộ trước
        mapping
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>{data.columns.map((column) => <th key={column}>{column}</th>)}</tr>
          </thead>
          <tbody>
            {data.sample_rows.slice(0, 5).map((row, index) => (
              <tr key={index}>
                {data.columns.map((column) => <td key={column}>{String(row[column] ?? "")}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}

