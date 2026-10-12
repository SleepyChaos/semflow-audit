import type { AuditRun } from "@/api/audits"
import type { StageRun } from "@/api/stages"

import { labelPhase, labelStatus } from "@/features/stages/stage-labels"
export function DiscoveryCoverage({
  run,
  stages,
}: {
  run: AuditRun
  stages: StageRun[]
}) {
  const dual = run.coverage.dual_engine
  const scouts = stages.filter((stage) => stage.kind === "scout")
  return (
    <section className="stage-section">
      <h3>双引擎发现与覆盖</h3>
      <p>
        CodeQL 静态扫描与 Agent
        独立粗筛分析同一源码快照。粗筛窗口已检查不代表该业务流程安全。
      </p>
      {dual ? (
        <p>
          整体：{labelStatus(dual.status)} · CodeQL：
          {labelStatus(dual.codeql?.status ?? "等待结果")} · Agent：
          {labelStatus(dual.scout?.status ?? "等待结果")}
        </p>
      ) : (
        <p>该历史任务仅包含静态扫描，可单独启动粗筛。</p>
      )}
      {scouts.map((stage) => (
        <details key={stage.id}>
          <summary>
            粗筛 {labelStatus(stage.status)} · {labelPhase(stage.phase)}
          </summary>
          {stage.error ? <p role="alert">{stage.error}</p> : null}
          <pre className="source-code">
            {JSON.stringify(
              stage.result.coverage ?? {
                status: stage.status,
                meaning: "尚未完成覆盖统计",
              },
              null,
              2,
            )}
          </pre>
        </details>
      ))}
    </section>
  )
}
