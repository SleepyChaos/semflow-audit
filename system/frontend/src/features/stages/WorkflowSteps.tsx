import { Check, Circle, LoaderCircle, TriangleAlert } from "lucide-react"

export interface WorkflowStep {
  title: string
  detail: string
  statusLabel?: string
  status: "waiting" | "active" | "done" | "attention"
}
export function WorkflowSteps({
  steps,
  label,
}: {
  steps: WorkflowStep[]
  label: string
}) {
  return (
    <ol className="workflow-steps" aria-label={label}>
      {steps.map((step, index) => {
        const Icon =
          step.status === "done"
            ? Check
            : step.status === "active"
              ? LoaderCircle
              : step.status === "attention"
                ? TriangleAlert
                : Circle
        return (
          <li
            key={step.title}
            data-status={step.status}
            aria-current={
              ["active", "attention"].includes(step.status) ? "step" : undefined
            }
          >
            <span className="workflow-step-icon">
              <Icon size={17} aria-hidden="true" />
            </span>
            <div>
              <strong>
                {index + 1}. {step.title}
                <span className="workflow-step-status">
                  {step.statusLabel ??
                    (step.status === "done"
                      ? "已完成"
                      : step.status === "attention"
                        ? "受阻"
                        : step.status === "active"
                          ? "待完成"
                          : "待开始")}
                </span>
              </strong>
              <p>{step.detail}</p>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
