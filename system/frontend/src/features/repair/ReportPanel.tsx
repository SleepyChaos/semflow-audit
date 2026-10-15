import type { AuditRun } from "@/api/audits"
import type { StageRun } from "@/api/stages"
import { StageHistory } from "@/features/stages/StageHistory"
import { AIReportPanel } from "./AIReportPanel"

export function ReportPanel({
  run,
  stages,
  modelReady,
}: {
  run: AuditRun
  stages: StageRun[]
  modelReady: boolean
}) {
  return (
    <section className="stage-section downstream-workspace">
      <AIReportPanel auditId={run.id} modelReady={modelReady} run={run} />
      <details className="downstream-disclosure">
        <summary>报告生成记录</summary>
        <StageHistory stages={stages} />
      </details>
    </section>
  )
}
