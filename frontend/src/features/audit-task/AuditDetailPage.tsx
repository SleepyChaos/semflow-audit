import { Link, useNavigate } from "@tanstack/react-router"
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
  if (data.audits.isPending) return <p role="status">正在读取审计任务…</p>
  if (data.audits.error)
    return (
      <div role="alert">
        <h1>无法读取审计任务</h1>
        <p>{data.audits.error.message}</p>
        <button type="button" onClick={() => data.audits.refetch()}>
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
            {data.run.status === "completed" ? data.run.findings.length : "—"}
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
          人工确认{" "}
          <strong>
            {summary?.confirmed ??
              (data.candidates.isError ? "无法读取" : "读取中")}
          </strong>
        </span>
        {action && action.stage !== stage && (
          <Link
            to="/audits/$auditId"
            params={{ auditId }}
            search={{ stage: action.stage }}
            title={action.reason}
          >
            {action.label} →
          </Link>
        )}
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
