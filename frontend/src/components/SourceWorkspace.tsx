import type { FormEvent } from "react";

type Props = {
  serviceReady: boolean;
  busy: boolean;
  ordersFile: File | null;
  bankFile: File | null;
  reopenId: string;
  onOrdersFile: (file: File | null) => void;
  onBankFile: (file: File | null) => void;
  onReopenId: (value: string) => void;
  onUpload: () => void;
  onDemo: () => void;
  onReopen: () => void;
};

function FileField({
  id,
  label,
  hint,
  file,
  onFile,
}: {
  id: string;
  label: string;
  hint: string;
  file: File | null;
  onFile: (file: File | null) => void;
}) {
  return (
    <label className={`file-field ${file ? "selected" : ""}`} htmlFor={id}>
      <span className="file-icon" aria-hidden="true">{file ? "✓" : "↑"}</span>
      <span className="file-copy">
        <strong>{label}</strong>
        <small>{file ? file.name : hint}</small>
      </span>
      <span className="file-action">{file ? "Đổi file" : "Chọn file"}</span>
      <input
        id={id}
        type="file"
        accept=".csv,.xlsx"
        onChange={(event) => onFile(event.target.files?.[0] ?? null)}
      />
    </label>
  );
}

export function SourceWorkspace(props: Props) {
  const canUpload = Boolean(props.ordersFile && props.bankFile && props.serviceReady && !props.busy);
  function submitUpload(event: FormEvent) {
    event.preventDefault();
    if (canUpload) props.onUpload();
  }
  function submitReopen(event: FormEvent) {
    event.preventDefault();
    if (props.reopenId.trim() && !props.busy) props.onReopen();
  }

  return (
    <section className="source-page" aria-labelledby="source-title">
      <div className="page-intro">
        <p className="eyebrow">ĐỐI SOÁT HAI NGUỒN · BẢO TOÀN TIỀN</p>
        <h1 id="source-title">Đối soát giao dịch tài chính</h1>
        <p>
          Kết nối khoản phải thu với giao dịch ngân hàng hoặc PSP, kiểm tra chất lượng dữ liệu
          và phân bổ tiền theo bằng chứng có thể truy vết.
        </p>
      </div>

      <div className="source-layout">
        <form className="surface upload-workspace" onSubmit={submitUpload}>
          <div className="surface-heading">
            <div><span className="section-index">01</span><div><h2>Tải lên dữ liệu</h2><p>Chọn đủ hai nguồn để bắt đầu khám phá dữ liệu.</p></div></div>
            <span className="required-note">2 file bắt buộc</span>
          </div>
          <div className="file-grid">
            <FileField id="orders-file" label="Khoản phải thu" hint="CSV hoặc XLSX" file={props.ordersFile} onFile={props.onOrdersFile} />
            <FileField id="bank-file" label="Ngân hàng / PSP" hint="CSV hoặc XLSX" file={props.bankFile} onFile={props.onBankFile} />
          </div>
          <div className="upload-requirements" aria-label="Yêu cầu upload">
            <span>CSV hoặc XLSX</span><span>Tối đa 25 MB mỗi file</span><span>Tối đa 100.000 dòng</span>
          </div>
          <p className="privacy-note"><span aria-hidden="true">◇</span> File được lưu trong artifact volume local, giữ nguyên bản gốc và không bị ghi đè.</p>
          <button className="primary upload-submit" type="submit" disabled={!canUpload}>
            {props.busy ? <><span className="spinner" aria-hidden="true" />Đang kiểm tra…</> : "Kiểm tra và xem trước"}
          </button>
        </form>

        <aside className="source-aside" aria-label="Tùy chọn khác">
          <article className="surface aside-card demo-card">
            <span className="section-index">DỮ LIỆU MẪU</span>
            <h2>Khám phá nhanh SmartRecon</h2>
            <p>Bộ VND synthetic có các ca 1:1, gộp, chia, thiếu, thừa và giao dịch mơ hồ.</p>
            <button className="secondary accent" type="button" disabled={props.busy || !props.serviceReady} onClick={props.onDemo}>
              {props.busy ? "Đang chuẩn bị…" : "Sử dụng dữ liệu mẫu"}
            </button>
          </article>
          <form className="surface aside-card reopen-card" onSubmit={submitReopen}>
            <span className="section-index">PHIÊN ĐÃ LƯU</span>
            <h2>Mở lại kết quả</h2>
            <label htmlFor="run-id">Run ID</label>
            <div className="inline-form">
              <input id="run-id" placeholder="Ví dụ: d450f6b2-…" value={props.reopenId} onChange={(event) => props.onReopenId(event.target.value)} />
              <button className="secondary" type="submit" disabled={props.busy || !props.reopenId.trim()}>Mở phiên</button>
            </div>
          </form>
        </aside>
      </div>
    </section>
  );
}
