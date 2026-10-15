import { useEffect } from "react";
import type { ReactNode } from "react";

export function DetailDrawer({ title, subtitle, onClose, children }: {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div className="drawer-layer" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="detail-drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <header className="drawer-header">
          <div><h2 id="drawer-title">{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
          <button className="drawer-close" type="button" onClick={onClose} aria-label="Đóng chi tiết">×</button>
        </header>
        <div className="drawer-body">{children}</div>
      </aside>
    </div>
  );
}
