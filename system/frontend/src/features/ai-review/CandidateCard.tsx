import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useId, useState } from "react"
import { toast } from "sonner"
import { classifyCandidate } from "@/api/review"
import type { Candidate } from "@/api/stages"
import { Button } from "@/components/ui/button"
import { WorkspaceSelect } from "@/components/WorkspaceSelect"
import { CandidateEvidence } from "./CandidateEvidence"
import { CandidateReviewSummary } from "./CandidateReviewSummary"
import { candidateSourceLabel, reviewVerdict } from "./review-status"

export function CandidateCard({
  candidate,
  busy,
}: {
  candidate: Candidate
  busy: boolean
}) {
  const selectionId = useId()
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
            {candidate.weakness} / {candidateSourceLabel(candidate)}
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
      {candidate.issue && candidate.issue.current_ids.length > 1 && (
        <p className="page-note">
          已将 {candidate.issue.current_ids.length}{" "}
          条同根因发现合并为一个漏洞，保留各来源的证据与执行记录。
          {candidate.issue.conflict &&
            "两路复核结论不一致，请核对证据后调整分类。"}
        </p>
      )}
      <div className="classification-controls">
        <label htmlFor={selectionId}>
          调整评价分类
          <WorkspaceSelect
            id={selectionId}
            className="native-select"
            value={status}
            onValueChange={setStatus}
            disabled={busy || mutation.isPending}
            options={[
              { value: "confirmed", label: "确认真实" },
              { value: "excluded", label: "确认误报" },
              { value: "insufficient", label: "证据不足" },
            ]}
          />
        </label>
        <Button
          variant="outline"
          disabled={
            busy ||
            mutation.isPending ||
            (status === candidate.classification?.status &&
              !candidate.issue?.conflict)
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
