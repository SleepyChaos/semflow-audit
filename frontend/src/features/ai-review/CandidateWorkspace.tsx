import { useState } from "react"
import type { Candidate, Evidence, StageRun } from "@/api/stages"
import { uniqueCandidates } from "@/features/audit-task/task-summary"
import { CandidateCard } from "./CandidateCard"
export const humanStatuses: Record<string, string> = {
  confirmed: "已确认",
  excluded: "支持排除",
  pending: "待确认",
  insufficient: "证据不足",
}
export function CandidateWorkspace({
  candidates,
  evidence,
  stages,
  busy,
}: {
  candidates: Candidate[]
  evidence: Evidence[]
  stages: StageRun[]
  busy: boolean
}) {
  const unique = uniqueCandidates(candidates),
    [selected, setSelected] = useState<string | null>(null)
  const candidate = unique.find((c) => c.id === selected) ?? unique[0]
  return (
    <div className="candidate-workspace" data-testid="candidate-workspace">
      <aside className="candidate-rail">
        <div className="rail-heading">
          待审候选 <span>{unique.length}</span>
        </div>
        {unique.map((c) => (
          <button
            type="button"
            className="candidate-option"
            aria-pressed={c.id === candidate?.id}
            key={c.id}
            onClick={() => setSelected(c.id)}
          >
            <span>{c.title}</span>
            <small>
              {c.weakness} · {humanStatuses[c.status] ?? c.status}
            </small>
            <small>
              {c.location.file ?? "位置待核实"}
              {c.location.line ? `:${c.location.line}` : ""}
            </small>
          </button>
        ))}
        {!unique.length && (
          <p className="page-note">
            暂无候选。可启动统一复核，或检查扫描覆盖范围。
          </p>
        )}
      </aside>
      {candidate ? (
        <CandidateCard
          key={`${candidate.id}:${candidate.status}`}
          candidate={candidate}
          evidence={evidence}
          busy={busy}
          stages={stages}
        />
      ) : (
        <div className="empty-state">
          <h3>等待证据</h3>
          <p>候选将在复核后显示，未报警不等于安全。</p>
        </div>
      )}
    </div>
  )
}
