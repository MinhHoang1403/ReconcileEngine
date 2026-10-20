import type { FormEvent } from "react";

type Props = {
  serviceReady: boolean;
  busy: boolean;
  ordersFile: File | null;
  bankFile: File | null;
  workbookFile: File | null;
  uploadMode: "files" | "workbook";
  ordersSheet: string;
  bankSheet: string;
  reopenId: string;
  onOrdersFile: (file: File | null) => void;
  onBankFile: (file: File | null) => void;
  onWorkbookFile: (file: File | null) => void;
  onUploadMode: (mode: "files" | "workbook") => void;
  onOrdersSheet: (value: string) => void;
  onBankSheet: (value: string) => void;
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
  const sheetSelectionValid = Boolean(props.ordersSheet) === Boolean(props.bankSheet);
  const hasSources = props.uploadMode === "files"
    ? Boolean(props.ordersFile && props.bankFile)
    : Boolean(props.workbookFile && sheetSelectionValid);
  const canUpload = Boolean(hasSources && props.serviceReady && !props.busy);
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
          Chọn dữ liệu đơn hàng và tiền đã nhận. Hệ thống tự kiểm tra, chỉ hỏi thêm khi chưa đủ thông tin
          và đối chiếu theo bằng chứng có thể truy vết.
        </p>
      </div>

      <div className="source-layout">
        <form className="surface upload-workspace" onSubmit={submitUpload}>
          <div className="surface-heading">
            <div><span className="section-index">01</span><div><h2>Tải lên dữ liệu</h2><p>Chọn hai file riêng hoặc một workbook chứa hai sheet.</p></div></div>
            <span className="required-note">2 nguồn bắt buộc</span>
          </div>
          <div className="upload-mode" role="group" aria-label="Cách tải dữ liệu">
            <button className={props.uploadMode === "files" ? "active" : ""} type="button" onClick={() => props.onUploadMode("files")}>Hai file riêng</button>
            <button className={props.uploadMode === "workbook" ? "active" : ""} type="button" onClick={() => props.onUploadMode("workbook")}>Một workbook</button>
          </div>
          {props.uploadMode === "files" ? (
            <div className="file-grid">
              <FileField id="orders-file" label="Danh sách đơn hàng cần thu tiền" hint="CSV hoặc XLSX" file={props.ordersFile} onFile={props.onOrdersFile} />
              <FileField id="bank-file" label="Danh sách giao dịch thanh toán" hint="CSV hoặc XLSX" file={props.bankFile} onFile={props.onBankFile} />
            </div>
          ) : (
            <div className="workbook-upload">
              <FileField id="workbook-file" label="Workbook chứa hai nguồn" hint="XLSX" file={props.workbookFile} onFile={props.onWorkbookFile} />
              <details>
                <summary>Chọn sheet thủ công nếu hệ thống không thể phân biệt</summary>
                <div className="sheet-fields">
                  <label><span>Sheet đơn hàng</span><input value={props.ordersSheet} onChange={(event) => props.onOrdersSheet(event.target.value)} placeholder="Để trống để tự nhận diện" /></label>
                  <label><span>Sheet giao dịch</span><input value={props.bankSheet} onChange={(event) => props.onBankSheet(event.target.value)} placeholder="Để trống để tự nhận diện" /></label>
                </div>
                {!sheetSelectionValid && <p className="field-error">Hãy nhập cả hai tên sheet hoặc để trống cả hai.</p>}
              </details>
            </div>
          )}
          <div className="source-descriptions">
            <p><strong>File đơn hàng:</strong> chứa thông tin đơn hàng và số tiền cần nhận.</p>
            <p><strong>File giao dịch:</strong> chứa các khoản tiền đã được ngân hàng hoặc cổng thanh toán ghi nhận.</p>
          </div>
          <div className="upload-requirements" aria-label="Yêu cầu upload">
            <span>CSV hoặc XLSX</span><span>Tối đa 25 MB mỗi file</span><span>Tối đa 100.000 dòng</span>
          </div>
          <p className="privacy-note"><span aria-hidden="true">◇</span> File được lưu trong artifact volume local, giữ nguyên bản gốc và không bị ghi đè.</p>
          <button className="primary upload-submit" type="submit" disabled={!canUpload}>
            {props.busy ? <><span className="spinner" aria-hidden="true" />Đang kiểm tra…</> : "Kiểm tra và xem trước"}
          </button>
          {props.busy && <p role="status">Đang nhận diện và kiểm tra toàn bộ dữ liệu. Chưa chạy đối soát.</p>}
        </form>

        <aside className="source-aside" aria-label="Tùy chọn khác">
          <article className="surface aside-card demo-card">
            <span className="section-index">DỮ LIỆU MẪU</span>
            <h2>Khám phá nhanh SmartRecon</h2>
            <p>Dùng dữ liệu mô phỏng để thử các tình huống thực tế: thanh toán một hoặc nhiều đơn, trả nhiều lần, trả thiếu, trả dư và giao dịch chưa rõ nguồn gốc cần kiểm tra.</p>
            <button className="secondary accent" type="button" disabled={props.busy || !props.serviceReady} onClick={props.onDemo}>
              {props.busy ? "Đang chuẩn bị…" : "Sử dụng dữ liệu mẫu"}
            </button>
          </article>
          <form className="surface aside-card reopen-card" onSubmit={submitReopen}>
            <span className="section-index">PHIÊN ĐÃ LƯU</span>
            <h2>Mở lại kết quả</h2>
            <label htmlFor="run-id">Mã phiên đối soát</label>
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
