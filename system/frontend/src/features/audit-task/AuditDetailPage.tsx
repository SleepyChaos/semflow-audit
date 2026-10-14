import { Link, useNavigate } from "@tanstack/react-router"
import { ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { reviewBlockReason } from "@/features/codeql-stage/discovery-state"
import { RunDetails } from "@/features/codeql-stage/RunDetails"
import {
  type AuditStage,
  auditStages,
  normalizeStage,
  stagePanels,
} from "@/features/shell/navigation"
import { PageHeader } from "@/features/shell/PageHeader"
import { getTaskAction, summarizeCandidates } from "./task-summary"
import { useAuditData } from "./useAuditData"
export function AuditDetailPage({
  auditId,
  stage,
}: {
  auditId: string
  stage: AuditStage
}) {
  const data = useAuditData(auditId)
  const navigate = useNavigate()
  const changeStage = (next: AuditStage) =>
    navigate({
      to: "/audits/$auditId",
      params: { auditId },
      search: { stage: next },
    })
  if (data.audit.isPending) return <p role="status">正在读取审计任务…</p>
  if (data.audit.error)
    return (
      <div role="alert">
        <h1>无法读取审计任务</h1>
        <p>{data.audit.error.message}</p>
        <button type="button" onClick={() => data.audit.refetch()}>
          重新读取
        </button>
      </div>
    )
  if (!data.run)
    return (
      <div className="empty-state">
        <h1>未找到审计任务</h1>
        <p>任务可能不属于当前独立工作台。</p>
        <Link to="/audits">返回任务列表</Link>
      </div>
    )
  const selected = auditStages.find((item) => item.id === stage)!
  const summary = data.candidates.isSuccess
    ? summarizeCandidates(data.candidates.data)
    : undefined
  const action = getTaskAction(data.run, data.candidates.data, data.stages.data)
  const reviewBlocked = reviewBlockReason(data.run, data.stages.data ?? [], {
    pending: data.stages.isPending,
    error: data.stages.error,
  })
  const reverse: Record<string, AuditStage> = {
    codeql: "scan",
    ai: "review",
    repair: "repair",
    rag: "rules",
  }
  return (
    <div className="page-stack">
      <PageHeader title={selected.title} description={selected.description} />
      <div className="task-summary-strip">
        <span>
          项目 <strong>{data.run.project_name}</strong>
        </span>
        <span>
          静态告警{" "}
          <strong>
            {data.run.coverage.dual_engine?.codeql?.status === "completed" ||
            data.run.status === "completed"
              ? data.run.findings.length
              : "—"}
          </strong>
        </span>
        <span>
          AI 候选{" "}
          <strong>
            {summary?.aiCandidates ??
              (data.candidates.isError ? "无法读取" : "读取中")}
          </strong>
        </span>
        <span>
          确认真实{" "}
          <strong>
            {summary?.confirmed ??
              (data.candidates.isError ? "无法读取" : "读取中")}
          </strong>
        </span>
        {stage === "scan" ? (
          <div className="task-summary-action">
            <Button
              size="lg"
              disabled={Boolean(reviewBlocked)}
              aria-describedby={
                reviewBlocked ? "review-block-reason" : undefined
              }
              onClick={() => changeStage("review")}
            >
              复核候选
              <ArrowRight data-icon="inline-end" />
            </Button>
            {reviewBlocked ? (
              <p id="review-block-reason" role="status">
                {reviewBlocked}
              </p>
            ) : null}
          </div>
        ) : action &&
          action.stage !== stage &&
          !["repair", "rules"].includes(stage) ? (
          <div className="task-summary-action">
            <Button asChild size="lg">
              <Link
                to="/audits/$auditId"
                params={{ auditId }}
                search={{ stage: action.stage }}
                title={action.reason}
              >
                {action.label}
                <ArrowRight data-icon="inline-end" />
              </Link>
            </Button>
          </div>
        ) : null}
      </div>
      <RunDetails
        run={data.run}
        activeStage={stagePanels[stage]}
        onStageChange={(value) => changeStage(normalizeStage(reverse[value]))}
        onCreated={(id) =>
          navigate({
            to: "/audits/$auditId",
            params: { auditId: id },
            search: { stage: "scan" },
          })
        }
      />
    </div>
  )
}
