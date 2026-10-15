export function AppHeader({ serviceReady, onReset }: { serviceReady: boolean; onReset: () => void }) {
  return (
    <header className="topbar">
      <button className="brand" type="button" onClick={onReset} aria-label="Về trang bắt đầu SmartRecon">
        <span className="brand-mark" aria-hidden="true">SR</span>
        <span className="brand-copy">
          <strong>SmartRecon</strong>
          <small>Trung tâm đối soát</small>
        </span>
      </button>
      <div
        className={`service-chip ${serviceReady ? "ready" : "offline"}`}
        role="status"
        aria-live="polite"
      >
        <span aria-hidden="true" />
        <div>
          <strong>{serviceReady ? "Hệ thống sẵn sàng" : "Mất kết nối backend"}</strong>
          <small>{serviceReady ? "API và cơ sở dữ liệu đang hoạt động" : "Kiểm tra Docker services"}</small>
        </div>
      </div>
    </header>
  );
}
