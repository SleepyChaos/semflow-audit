import { Link } from "@tanstack/react-router"
import type { AuditRun } from "@/api/audits"
import type { StageRun } from "@/api/stages"
import { Button } from "@/components/ui/button"
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
      <div className="downstream-section-heading">
        <div>
          <h3>基于完整复审结果的审计报告</h3>
          <p>
            汇总真实漏洞、误报与证据不足的分类、判断依据、项目利用用例、关联源码和未检查范围，无需先选择修复目标。
          </p>
        </div>
        <Button asChild variant="outline">
          <Link
            to="/audits/$auditId"
            params={{ auditId: run.id }}
            search={{ stage: "repair" }}
          >
            选择漏洞修复 →
          </Link>
        </Button>
      </div>
      <AIReportPanel auditId={run.id} modelReady={modelReady} />
      <details className="downstream-disclosure">
        <summary>报告生成记录</summary>
        <StageHistory stages={stages} />
      </details>
    </section>
  )
}
