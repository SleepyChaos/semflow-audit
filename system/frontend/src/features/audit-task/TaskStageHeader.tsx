import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { ArrowRight } from "lucide-react"
import type { AuditRun } from "@/api/audits"
import { getRepairs, getReport, getRules, type StageRun } from "@/api/stages"
import { Button } from "@/components/ui/button"
import {
  currentReviewCandidates,
  reviewVerdict,
} from "@/features/ai-review/review-status"
import {
  activeStatus,
  codeqlStatus,
  currentScout,
  reviewBlockReason,
  scoutProgress,
} from "@/features/codeql-stage/discovery-state"
import { type AuditStage, auditStages } from "@/features/shell/navigation"
import {
  repairProgress,
  ruleProgress,
} from "@/features/stages/downstream-progress"
import { labelPhase, labelStatus } from "@/features/stages/stage-labels"
import { WorkflowSteps } from "@/features/stages/WorkflowSteps"
import type { useAuditData } from "./useAuditData"

type Data = ReturnType<typeof useAuditData>
type Summary = { title: string; detail: string }
const newest = (stages: StageRun[], kinds: string[]) =>
  [...stages]
    .filter((s) => kinds.includes(s.kind))
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))[0]

function discoverySummary(run: AuditRun, data: Data): Summary {
  if (data.stages.error)
    return {
      title: "初审状态读取失败",
      detail: "请在下方重新读取状态，暂不能判断审计是否完成。",
    }
  if (data.stages.isPending)
    return {
      title: "正在读取审计进展",
      detail: "静态分析与 AI 初审结果将自动更新。",
    }
  const codeql = codeqlStatus(run)
  const scout = scoutProgress(run, currentScout(run, data.stages.data ?? []))
  const complete =
    codeql === "completed" && ["completed", "not_run"].includes(scout.status)
  return {
    title:
      activeStatus(run.status) || activeStatus(codeql) || scout.busy
        ? "正在执行初步审计"
        : complete
          ? "初步审计完成"
          : "初步审计尚未完整完成",
    detail: `CodeQL：${codeql === "completed" ? `${run.findings.length} 条静态告警` : labelStatus(codeql)} · AI 初审：${scout.total !== undefined ? `${scout.completed} / ${scout.total} 个窗口` : labelStatus(scout.status)}${scout.status === "partial" ? "，仍有范围未检查" : ""}`,
  }
}

function reviewSummary(data: Data): Summary {
  if (data.stages.error || data.candidates.error)
    return {
      title: "复核结果读取失败",
      detail: "暂时无法汇总复核情况，请重新读取。",
    }
  if (data.stages.isPending || data.candidates.isPending)
    return { title: "正在读取复核情况", detail: "等待已保存的分类与复核结果。" }
  const stage = newest(data.stages.data ?? [], ["review"])
  const counts = { supported: 0, insufficient: 0, excluded: 0, neutral: 0 }
  for (const candidate of currentReviewCandidates(data.candidates.data ?? [])) {
    const tone = reviewVerdict(candidate).tone as keyof typeof counts
    counts[tone]++
  }
  const missing = stage?.result.unreviewed_candidate_ids
  const incomplete = Array.isArray(missing) && missing.length > 0
  const title = !stage
    ? "尚未启动统一复核"
    : activeStatus(stage.status)
      ? "正在复核漏洞候选"
      : stage.status === "failed"
        ? "本次复核失败"
        : stage.status === "cancelled"
          ? "本次复核已取消"
          : incomplete
            ? "复核结束，仍有未评估项"
            : "复核结果已生成"
  return {
    title,
    detail: `确认真实 ${counts.supported} · 证据不足 ${counts.insufficient} · 确认误报 ${counts.excluded}${counts.neutral ? ` · 待复核 ${counts.neutral}` : ""}${incomplete ? ` · ${missing.length} 项未评估` : ""}`,
  }
}

export function TaskStageHeader({
  run,
  stage,
  data,
}: {
  run: AuditRun
  stage: AuditStage
  data: Data
}) {
  const navigate = useNavigate()
  const stages = data.stages.data ?? []
  const active = stages.some((s) => activeStatus(s.status))
  const report = useQuery({
    queryKey: ["report", run.id],
    queryFn: () => getReport(run.id),
    enabled: stage === "report",
    refetchInterval: (q) =>
      stage === "report" && activeStatus(q.state.data?.ai_report?.status)
        ? 2000
        : false,
  })
  const repairs = useQuery({
    queryKey: ["repairs", run.id],
    queryFn: () => getRepairs(run.id),
    enabled: stage === "repair",
    refetchInterval: stage === "repair" && active ? 2500 : false,
  })
  const rules = useQuery({
    queryKey: ["rules", run.language],
    queryFn: () => getRules(run.language),
    enabled: stage === "rules",
    refetchInterval: stage === "rules" && active ? 3000 : false,
  })
  const reportSummary = (): Summary => {
    if (report.error)
      return {
        title: "报告读取失败",
        detail: "报告状态暂时无法读取，请在下方重试。",
      }
    if (report.isPending)
      return {
        title: "正在读取报告状态",
        detail: "等待当前审计结果对应的报告。",
      }
    const ai = report.data?.ai_report
    const counts = report.data?.summary?.candidate_states
    const labels: Record<string, string> = {
      ready: "审计报告已生成",
      running: "正在生成审计报告",
      queued: "报告等待生成",
      failed: "本次报告生成失败",
      stale: "复审结果已更新，报告需要重新生成",
      cancelled: "报告生成已取消",
    }
    return {
      title: labels[ai?.status ?? ""] ?? "尚未生成审计报告",
      detail:
        ai?.status === "ready"
          ? counts
            ? `确认真实 ${counts.confirmed ?? 0} · 证据不足 ${counts.insufficient ?? 0} · 确认误报 ${counts.excluded ?? 0}${counts.pending ? ` · 待复核 ${counts.pending}` : ""} · 完整报告可下载`
            : `已汇总 ${ai.narrative?.issues.length ?? 0} 项候选，可查看详情或下载完整报告。`
          : ai?.status === "failed"
            ? "报告生成未完成，原有复审结论和证据保留。可在下方重试，或先导出 JSON / SARIF。"
            : ai?.status === "stale"
              ? "上游结果已变化，请重新生成报告；旧报告不作为当前审计结论。"
              : "汇总复审分类、判断依据、利用用例与证据；无需先生成修复补丁。",
    }
  }
  const repairSummary = (): Summary => {
    if (repairs.error || data.stages.error)
      return {
        title: "修复状态读取失败",
        detail: "暂时无法判断补丁与验证进展。",
      }
    if (repairs.isPending || data.stages.isPending)
      return {
        title: "正在读取修复进展",
        detail: "等待已保存的补丁与验证结果。",
      }
    const current = newest(stages, [
      "repair",
      "verification",
      "verification_suite",
      "verification_acceptance",
    ])
    const records = repairs.data ?? []
    const accepted = records.filter((r) => r.status === "accepted").length
    return {
      title:
        current && activeStatus(current.status)
          ? labelPhase(current.phase)
          : current?.status === "failed"
            ? "本次修复或验证执行失败"
            : accepted
              ? "已有已接受的修复补丁"
              : records.length
                ? "补丁已生成，请核对 Diff 与验证结果"
                : "尚未生成修复补丁",
      detail: `${records.length} 次修复尝试 · ${accepted} 份补丁已接受。仅可选择确认真实的漏洞，原始源码保持不变。`,
    }
  }
  const ruleSummary = (): Summary => {
    if (rules.error || data.stages.error)
      return {
        title: "规则状态读取失败",
        detail: "暂时无法汇总规则与验收结果。",
      }
    if (rules.isPending || data.stages.isPending)
      return {
        title: "正在读取规则进展",
        detail: "等待已保存的规则与验收结果。",
      }
    const current = newest(stages, ["rule"])
    const rows = (rules.data ?? []).filter((r) => r.audit_id === run.id)
    const published = rows.filter((r) => r.status === "published").length
    return {
      title:
        current && activeStatus(current.status)
          ? labelPhase(current.phase)
          : current?.status === "failed"
            ? "本次规则执行失败"
            : current?.status === "awaiting_confirmation"
              ? "规则草稿等待验收"
              : rows.length
                ? "规则结果已保存"
                : "尚未生成审计规则",
      detail: `本任务 ${rows.length} 个规则版本 · ${published} 个已发布。验收通过后可发布并复用于新审计。`,
    }
  }
  const summary =
    stage === "scan"
      ? discoverySummary(run, data)
      : stage === "review"
        ? reviewSummary(data)
        : stage === "report"
          ? reportSummary()
          : stage === "repair"
            ? repairSummary()
            : ruleSummary()
  const workflow =
    stage === "repair"
      ? repairProgress(stages, repairs.data ?? [])
      : stage === "rules"
        ? ruleProgress(
            stages,
            (rules.data ?? []).filter((row) => row.audit_id === run.id),
          )
        : null
  const next = auditStages[auditStages.findIndex((s) => s.id === stage) + 1]
  const labels: Record<AuditStage, string> = {
    scan: "复核候选",
    review: "前往审计报告",
    report: "选择漏洞修复",
    repair: "前往规则生成",
    rules: "查看规则库",
  }
  const blocked =
    stage === "scan"
      ? reviewBlockReason(run, stages, {
          pending: data.stages.isPending,
          error: data.stages.error,
        })
      : null
  return (
    <section
      className="task-summary-strip task-stage-strip"
      aria-label="当前节点状态与下一步"
    >
      <div className="task-stage-status" role="status">
        <strong>{summary.title}</strong>
        <p>{summary.detail}</p>
      </div>
      <div className="task-summary-action">
        <Button
          size="lg"
          disabled={Boolean(blocked)}
          aria-describedby={blocked ? "stage-next-blocked" : undefined}
          onClick={() =>
            next
              ? navigate({
                  to: "/audits/$auditId",
                  params: { auditId: run.id },
                  search: { stage: next.id },
                })
              : navigate({ to: "/rules" })
          }
        >
          {labels[stage]}
          <ArrowRight data-icon="inline-end" />
        </Button>
        {blocked ? <p id="stage-next-blocked">{blocked}</p> : null}
      </div>
      {workflow && (
        <WorkflowSteps
          steps={workflow}
          label={stage === "repair" ? "代码修复流程" : "规则生成流程"}
        />
      )}
    </section>
  )
}
