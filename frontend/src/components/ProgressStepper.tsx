export type WorkflowStep = "source" | "mapping" | "health" | "dashboard";

const steps: { id: WorkflowStep; label: string; helper: string }[] = [
  { id: "source", label: "Nguồn dữ liệu", helper: "Chọn hai feed" },
  { id: "mapping", label: "Khám phá & ánh xạ", helper: "Kiểm tra cấu trúc" },
  { id: "health", label: "Chất lượng & đối soát", helper: "Xác minh dữ liệu" },
  { id: "dashboard", label: "Kết quả & báo cáo", helper: "Tra cứu và xuất" },
];

export function ProgressStepper({ current }: { current: WorkflowStep }) {
  const currentIndex = steps.findIndex((step) => step.id === current);
  return (
    <nav className="workflow-progress" aria-label="Tiến trình đối soát">
      <ol>
        {steps.map((step, index) => {
          const state = index < currentIndex ? "completed" : index === currentIndex ? "current" : "upcoming";
          return (
            <li className={`progress-step ${state}`} key={step.id} aria-current={state === "current" ? "step" : undefined}>
              <span className="step-number" aria-hidden="true">{state === "completed" ? "✓" : index + 1}</span>
              <span className="step-copy"><strong>{step.label}</strong><small>{step.helper}</small></span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
