import { Check } from "lucide-react"
import type { StageRun } from "@/api/stages"
import { cn } from "@/lib/utils"

const stages = [
  { id: "codeql", name: "CodeQL 审计" },
  { id: "ai", name: "AI 复审" },
  { id: "repair", name: "修复与报告" },
  { id: "rag", name: "RAG 规则" },
]
export function Pipeline({
  completed = false,
  active = "codeql",
  history = [],
  onSelect,
}: {
  completed?: boolean
  active?: string
  history?: StageRun[]
  onSelect?: (stage: string) => void
}) {
  const finished = [
    completed,
    history.some(
      (item) => item.kind === "review" && item.status === "completed",
    ),
    history.some(
      (item) => item.kind === "repair" && item.status === "completed",
    ),
    history.some((item) => item.kind === "rule" && item.status === "completed"),
  ]
  return (
    <ol className="pipeline" aria-label="审计流水线">
      {stages.map((stage, index) => (
        <li
          key={stage.id}
          className={cn(
            "pipeline-step",
            active === stage.id && "pipeline-active",
          )}
        >
          <button
            type="button"
            className="pipeline-number"
            onClick={() => onSelect?.(stage.id)}
            aria-label={`查看${stage.name}`}
            aria-current={active === stage.id ? "step" : undefined}
          >
            {finished[index] ? <Check size={18} /> : index + 1}
          </button>
          <span>{stage.name}</span>
        </li>
      ))}
    </ol>
  )
}
