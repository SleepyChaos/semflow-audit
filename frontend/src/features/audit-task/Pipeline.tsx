import { Check } from "lucide-react"
import { cn } from "@/lib/utils"
const stages = ["CodeQL 审计", "AI 复审", "修复与报告", "RAG 规则"]
export function Pipeline({ completed = false }: { completed?: boolean }) {
  return (
    <ol className="pipeline" aria-label="审计流水线">
      {stages.map((name, index) => (
        <li
          key={name}
          className={cn("pipeline-step", index === 0 && "pipeline-active")}
        >
          <span className="pipeline-number">
            {index === 0 && completed ? <Check size={18} /> : index + 1}
          </span>
          <span>{name}</span>
        </li>
      ))}{" "}
    </ol>
  )
}
