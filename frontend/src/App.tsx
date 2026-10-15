import { useEffect, useState } from "react";
import { fetchHealth } from "./api/health";
import "./styles.css";

type ServiceState = "checking" | "ready" | "unavailable";

export function App() {
  const [serviceState, setServiceState] = useState<ServiceState>("checking");

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then(() => setServiceState("ready"))
      .catch(() => setServiceState("unavailable"));
    return () => controller.abort();
  }, []);

  const serviceLabel = {
    checking: "Đang kiểm tra dịch vụ…",
    ready: "Backend và PostgreSQL đã sẵn sàng",
    unavailable: "Dịch vụ chưa sẵn sàng",
  }[serviceState];

  return (
    <main className="shell">
      <header>
        <p className="eyebrow">SMART FINANCIAL RECONCILIATION</p>
        <h1>Đối soát dòng tiền có bằng chứng</h1>
        <p className="intro">
          Chuẩn hóa khoản phải thu và giao dịch ngân hàng, bảo toàn từng đơn vị tiền,
          đồng thời giữ đầy đủ dấu vết giải thích.
        </p>
      </header>
      <section className="status-card" aria-live="polite">
        <span className={`status-dot status-${serviceState}`} />
        <div>
          <strong>Trạng thái hệ thống</strong>
          <p>{serviceLabel}</p>
        </div>
      </section>
    </main>
  );
}

