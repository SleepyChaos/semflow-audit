import { useQuery } from "@tanstack/react-query"
import { ChevronDown, SquareTerminal } from "lucide-react"
import { type ReactNode, useState } from "react"
import { getLogs } from "@/api/audits"
import { getStageLogs, getStages, type StageRun } from "@/api/stages"
import { Badge } from "@/components/ui/badge"
import { useAudit } from "@/features/audit-task/useAuditData"
import {
  activeStatus,
  codeqlStatus,
  currentScout,
  scoutProgress,
} from "@/features/codeql-stage/discovery-state"
import { labelPhase, labelStatus } from "@/features/stages/stage-labels"

function LogDisclosure({
  title,
  status,
  queryKey,
  load,
  available = true,
  unavailableMessage,
  children,
}: {
  title: string
  status: string
  queryKey: string[]
  load: () => Promise<{ text: string }>
  available?: boolean
  unavailableMessage?: string
  children?: ReactNode
}) {
  const [open, setOpen] = useState(false)
  const logs = useQuery({
    queryKey: [...queryKey, status],
    queryFn: load,
    enabled: open && available,
    retry: 1,
    refetchInterval: open && activeStatus(status) ? 2500 : false,
  })
  return (
    <details
      className="toolbar-execution-log"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <SquareTerminal size={16} aria-hidden="true" />
        <span>{title}</span>
        <Badge variant={status === "failed" ? "destructive" : "outline"}>
          {labelStatus(status)}
        </Badge>
        <ChevronDown size={16} aria-hidden="true" />
      </summary>
      <section
        className="toolbar-log-body"
        aria-label={title}
        // biome-ignore lint/a11y/noNoninteractiveTabindex: Keyboard users must be able to scroll this named log region.
        tabIndex={0}
      >
        {!available ? (
          <p>{unavailableMessage}</p>
        ) : logs.isPending ? (
          <p role="status">正在读取日志…</p>
        ) : logs.error ? (
          <p role="alert">日志读取失败：{logs.error.message}</p>
        ) : (
          <pre>{logs.data?.text || "当前暂无文本执行日志。"}</pre>
        )}
        {children}
      </section>
    </details>
  )
}

function ScoutExecutionRecords({ stage }: { stage: StageRun }) {
  const units = Array.isArray(stage.result.units)
    ? stage.result.units.filter(
        (unit): unit is Record<string, unknown> =>
          Boolean(unit) && typeof unit === "object" && !Array.isArray(unit),
      )
    : []
  return (
    <div className="scout-execution-records">
      <h4>已保存的初审执行记录</h4>
      <p>
        {labelPhase(stage.phase)} · {labelStatus(stage.status)}
      </p>
      {stage.error ? <p role="alert">{stage.error}</p> : null}
      {(stage.model_calls ?? []).map((call, index) => (
        <p key={String(call.call_index ?? index)}>
          调用 {String(call.call_index ?? index + 1)}
          {" · "}
          {call.error_code
            ? `失败：${String(call.error_code)}`
            : "已返回模型结果"}
          {" · "}耗时{" "}
          {typeof call.seconds === "number"
            ? `${call.seconds.toFixed(1)}s`
            : "未记录"}
          {" · "}输入 / 输出 token：{String(call.input_tokens ?? "未知")} /{" "}
          {String(call.output_tokens ?? "未知")}
        </p>
      ))}
      {units.map((unit, index) => (
        <p key={String(unit.unit_id ?? index)}>
          窗口 {String(unit.unit_id ?? index + 1)} ·{" "}
          {unit.status === "inspected" ? "已检查" : "未完成"}
          {unit.reason ? ` · ${String(unit.reason)}` : ""}
        </p>
      ))}
      {!stage.model_calls?.length && !units.length ? (
        <p>尚未保存模型调用或窗口检查记录。</p>
      ) : null}
    </div>
  )
}

export function AuditExecutionLogs({ auditId }: { auditId: string }) {
  const audit = useAudit(auditId)
  const run = audit.data
  const stages = useQuery({
    queryKey: ["stages", auditId],
    queryFn: () => getStages(auditId),
    enabled: Boolean(run),
    retry: 1,
    refetchInterval: (query) =>
      activeStatus(run?.status) ||
      query.state.data?.some((stage) => activeStatus(stage.status))
        ? 2500
        : false,
  })
  if (!run) return null
  const scout = currentScout(run, stages.data ?? [])
  const progress = scoutProgress(run, scout)
  return (
    <section className="audit-log-toolbar" aria-label="审计执行日志">
      <div className="audit-log-disclosures">
        <LogDisclosure
          key={`codeql:${auditId}`}
          title="CodeQL 执行日志"
          status={codeqlStatus(run)}
          queryKey={["logs", auditId]}
          load={() => getLogs(auditId)}
        />
        <LogDisclosure
          key={`scout:${auditId}:${scout?.id ?? "pending"}`}
          title="AI 初审执行日志"
          status={
            stages.error
              ? "unknown"
              : stages.isPending
                ? "queued"
                : progress.status
          }
          queryKey={["stage-logs", scout?.id ?? auditId]}
          available={Boolean(scout)}
          unavailableMessage={
            stages.error
              ? "尚未获得初审阶段，无法读取执行日志。"
              : stages.isPending
                ? "正在读取初审阶段…"
                : progress.status === "not_run"
                  ? "该任务未执行 AI 初审。"
                  : progress.status === "unknown"
                    ? "尚未获得初审阶段，请核对执行状态。"
                    : "等待初审阶段创建后读取日志。"
          }
          load={() => getStageLogs(scout!.id)}
        >
          {stages.error ? (
            <p role="alert">初审状态读取失败：{stages.error.message}</p>
          ) : null}
          {scout ? <ScoutExecutionRecords stage={scout} /> : null}
        </LogDisclosure>
      </div>
    </section>
  )
}
