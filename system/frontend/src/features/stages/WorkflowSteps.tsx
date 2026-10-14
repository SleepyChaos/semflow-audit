import { Check, Circle, LoaderCircle, TriangleAlert } from "lucide-react"

export interface WorkflowStep {
  title: string
  detail: string
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
            aria-current={step.status === "active" ? "step" : undefined}
          >
            <span className="workflow-step-icon">
              <Icon size={17} aria-hidden="true" />
            </span>
            <div>
              <strong>
                {index + 1}. {step.title}
              </strong>
              <p>{step.detail}</p>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
