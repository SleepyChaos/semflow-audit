import { useState } from "react"
import type { Candidate } from "@/api/stages"
import { CandidateCard } from "./CandidateCard"
import {
  candidateSourceLabel,
  currentReviewCandidates,
  reviewVerdict,
} from "./review-status"
export const humanStatuses: Record<string, string> = {
  confirmed: "已确认",
  excluded: "支持排除",
  pending: "待确认",
  insufficient: "证据不足",
}
export function CandidateWorkspace({
  candidates,
  busy,
}: {
  candidates: Candidate[]
  busy: boolean
}) {
  const unique = currentReviewCandidates(candidates),
    [selected, setSelected] = useState<string | null>(null)
  const candidate = unique.find((c) => c.id === selected) ?? unique[0]
  return (
    <div className="candidate-workspace" data-testid="candidate-workspace">
      <aside className="candidate-rail" aria-label="漏洞列表">
        <div className="rail-heading">
          漏洞列表 <span>{unique.length}</span>
        </div>
        {unique.map((c) => (
          <button
            type="button"
            className="candidate-option"
            data-verdict={reviewVerdict(c).tone}
            aria-pressed={c.id === candidate?.id}
            key={c.id}
            onClick={() => setSelected(c.id)}
          >
            <span>{c.review?.detail?.title ?? c.title}</span>
            <span
              className="review-verdict-badge"
              data-verdict={reviewVerdict(c).tone}
            >
              {reviewVerdict(c).label}
            </span>
            <small>
              {candidateSourceLabel(c)}
              {c.issue && c.issue.current_ids.length > 1
                ? ` · 已合并 ${c.issue.current_ids.length} 条发现`
                : ""}
            </small>
            <small>
              {c.weakness} ·{" "}
              {c.classification?.source === "human"
                ? "人工调整"
                : c.classification?.source === "ai"
                  ? "AI 自动分类"
                  : "待自动复核"}
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
      <section
        className="candidate-detail-scroll"
        aria-label="漏洞详情"
        key={candidate?.id ?? "empty"}
      >
        {candidate ? (
          <CandidateCard
            key={`${candidate.id}:${candidate.classification?.status}:${candidate.classification?.source}`}
            candidate={candidate}
            busy={busy}
          />
        ) : (
          <div className="empty-state">
            <h3>等待证据</h3>
            <p>候选将在复核后显示，未报警不等于安全。</p>
          </div>
        )}
      </section>
    </div>
  )
}
