import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { classifyCandidate } from "@/api/review"
import type { Candidate } from "@/api/stages"
import { Button } from "@/components/ui/button"
import { CandidateEvidence } from "./CandidateEvidence"
import { CandidateReviewSummary } from "./CandidateReviewSummary"
import { reviewVerdict } from "./review-status"

export function CandidateCard({
  candidate,
  busy,
}: {
  candidate: Candidate
  busy: boolean
}) {
  const [status, setStatus] = useState(
    candidate.classification?.status === "pending"
      ? "insufficient"
      : (candidate.classification?.status ?? "insufficient"),
  )
  const cache = useQueryClient()
  const verdict = reviewVerdict(candidate)
  const mutation = useMutation({
    mutationFn: () => classifyCandidate(candidate.id, status),
    onSuccess: async () => {
      await Promise.all([
        cache.invalidateQueries({
          queryKey: ["candidates", candidate.audit_id],
        }),
        cache.invalidateQueries({ queryKey: ["report", candidate.audit_id] }),
      ])
      toast.success("评价分类已更新")
    },
  })
  return (
    <article className="candidate-card evidence-workspace">
      <header>
        <div>
          <span className="eyebrow">
            {candidate.weakness} /{" "}
            {candidate.origin === "ai" ? "AI 候选" : "静态告警"}
          </span>
          <h3>{candidate.review?.detail?.title ?? candidate.title}</h3>
        </div>
        <span className="review-verdict-badge" data-verdict={verdict.tone}>
          {candidate.classification?.source === "human"
            ? "人工调整"
            : "AI 复核"}{" "}
          · {verdict.label}
        </span>
      </header>
      <div className="classification-controls">
        <label>
          调整评价分类
          <select
            className="native-select"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            disabled={busy || mutation.isPending}
          >
            <option value="confirmed">确认真实</option>
            <option value="excluded">确认误报</option>
            <option value="insufficient">证据不足</option>
          </select>
        </label>
        <Button
          variant="outline"
          disabled={
            busy ||
            mutation.isPending ||
            status === candidate.classification?.status
          }
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? "正在保存…" : "保存分类"}
        </Button>
        {mutation.error ? (
          <p role="alert">调整失败：{mutation.error.message}</p>
        ) : null}
      </div>
      <p className="page-note">
        默认采用 AI 复核分类，你只需在判断不符时调整分类。
      </p>
      <CandidateReviewSummary candidate={candidate} />
      <CandidateEvidence candidate={candidate} busy={busy} />
    </article>
  )
}
