import type { AuditRun } from "@/api/audits"
import type { StageRun } from "@/api/stages"

export const activeStatus = (status?: string) =>
  status === "queued" || status === "running"

const record = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
const rows = (value: unknown) => (Array.isArray(value) ? value.map(record) : [])
const count = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value) && value >= 0
    ? value
    : undefined

export function currentScout(run: AuditRun, stages: StageRun[]) {
  const scouts = stages.filter(
    (stage) => stage.audit_id === run.id && stage.kind === "scout",
  )
  // A separately requested rerun supersedes the initial dual-engine attempt.
  const latest = scouts.reduce<StageRun | undefined>(
    (selected, stage) =>
      !selected || stage.created_at > selected.created_at ? stage : selected,
    undefined,
  )
  const initialId =
    run.coverage.dual_engine?.scout_stage_id ??
    run.coverage.dual_engine?.scout?.stage_id
  return latest ?? scouts.find((stage) => stage.id === initialId)
}

export function scoutProgress(run: AuditRun, stage?: StageRun) {
  const dual = run.coverage.dual_engine
  const initialId = dual?.scout_stage_id ?? dual?.scout?.stage_id
  const fallback = !stage || stage.id === initialId ? dual?.scout : undefined
  const coverage = record(stage?.result.coverage ?? fallback?.coverage)
  const units = rows(stage?.result.units)
  const completed =
    count(coverage.inspected_windows) ??
    units.filter((unit) => unit.status === "inspected").length
  const total = count(coverage.planned_windows)
  const status =
    stage?.status ??
    fallback?.status ??
    (dual ? (activeStatus(run.status) ? "queued" : "unknown") : "not_run")
  const partial = status === "completed" && coverage.status === "partial"
  const incomplete = units.filter((unit) => unit.status === "incomplete")
  const stop = String(coverage.stop_reason ?? "")
  const stopLabels: Record<string, string> = {
    budget_exhausted: "模型调用预算耗尽，剩余范围未检查",
    timeout: "模型调用超时，剩余范围未检查",
    provider_error: "模型服务异常，剩余范围未检查",
  }
  return {
    status: partial ? "partial" : status,
    busy: activeStatus(status),
    completed,
    total,
    remaining: count(coverage.uninspected_windows),
    continuable:
      count(coverage.continuable_windows) ??
      (coverage.business_coverage_status === "completed" ? 0 : undefined),
    calls: stage?.model_calls?.length,
    stop: stopLabels[stop] ?? (stop ? `停止原因：${stop}` : undefined),
    error: stage?.error ?? fallback?.error,
    incomplete,
    files: rows(coverage.files).map((file) => ({
      name: String(file.file ?? "未知文件"),
      completed: count(file.inspected_windows),
      total: count(file.total_windows),
    })),
  }
}

export function scoutSourceIds(run: AuditRun, stage: StageRun | undefined) {
  const id =
    stage?.id ??
    run.coverage.dual_engine?.scout_stage_id ??
    run.coverage.dual_engine?.scout?.stage_id
  const inherited =
    stage?.result.snapshot_hash === run.snapshot_hash &&
    Array.isArray(stage.result.source_stage_ids)
      ? stage.result.source_stage_ids
      : []
  return new Set([
    id,
    ...inherited.filter((value): value is string => typeof value === "string"),
  ])
}

export function codeqlStatus(run: AuditRun) {
  if (run.coverage.dual_engine?.codeql?.status)
    return run.coverage.dual_engine.codeql.status
  if (
    ["codeql_ready", "discovery_ready", "discovery_partial"].includes(
      run.phase,
    ) &&
    !run.error
  )
    return "completed"
  return run.status
}

export function reviewBlockReason(
  run: AuditRun,
  stages: StageRun[],
  state: { pending?: boolean; error?: Error | null } = {},
): string | null {
  if (state.error) return "初审状态读取失败，重新读取后可复核。"
  if (state.pending) return "正在读取初审状态，请稍候。"
  const codeql = codeqlStatus(run)
  const scout = scoutProgress(run, currentScout(run, stages))
  if (activeStatus(codeql) && scout.busy)
    return "等待 CodeQL 和 AI 初审结束后复核。"
  if (activeStatus(codeql)) return "等待 CodeQL 静态分析结束后复核。"
  if (scout.busy) return "等待 AI 初审结束后复核。"
  // The run remains active until both initial branches have joined.
  if (activeStatus(run.status)) return "等待初步审计汇总结束后复核。"
  if (scout.status === "unknown")
    return "尚未获得 AI 初审状态，请先核对执行结果。"
  if (run.status === "cancelled") return "审计已取消，请重新执行后复核。"
  if (run.status === "completed" || run.coverage.dual_engine?.review_ready)
    return null
  return "初步审计未就绪，请先处理执行失败。"
}
