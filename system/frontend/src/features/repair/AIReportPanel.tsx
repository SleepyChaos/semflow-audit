import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Download } from "lucide-react"
import { useEffect, useState } from "react"
import { toast } from "sonner"
import { type AuditRun, downloadSarif } from "@/api/audits"
import {
  downloadReport,
  downloadReportJson,
  getReport,
  startReport,
} from "@/api/stages"
import { Button } from "@/components/ui/button"
import { codeqlStatus } from "@/features/codeql-stage/discovery-state"
import { ReportWorkspace } from "./ReportWorkspace"

export function AIReportPanel({
  auditId,
  modelReady,
  run,
}: {
  auditId: string
  modelReady: boolean
  run: AuditRun
}) {
  const cache = useQueryClient()
  const [pendingDownload, setPendingDownload] = useState(false)
  const report = useQuery({
    queryKey: ["report", auditId],
    queryFn: () => getReport(auditId),
    refetchInterval: (query) =>
      ["queued", "running"].includes(
        query.state.data?.ai_report?.status ?? "",
      ) || pendingDownload
        ? 2000
        : 10000,
  })
  const generate = useMutation({
    mutationFn: (force: boolean) => startReport(auditId, force),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => {
      setPendingDownload(false)
      toast.error(error.message)
    },
  })
  const ai = report.data?.ai_report
  const busy =
    generate.isPending || ["queued", "running"].includes(ai?.status ?? "")
  const narrative = ai?.status === "ready" ? ai.narrative : null
  const candidates = report.data?.candidates ?? []
  useEffect(() => {
    if (!pendingDownload || generate.isPending) return
    if (ai?.status === "ready") {
      setPendingDownload(false)
      downloadReport(auditId).catch((error: Error) =>
        toast.error(error.message),
      )
    } else if (
      ["failed", "cancelled"].includes(ai?.status ?? "") ||
      report.error
    ) {
      setPendingDownload(false)
      toast.error(
        ai?.error ??
          report.error?.message ??
          "AI 中文报告未生成，请查看执行结果并重试",
      )
    }
  }, [
    ai?.status,
    ai?.error,
    auditId,
    pendingDownload,
    report.error,
    generate.isPending,
  ])
  const exportMarkdown = () => {
    if (narrative)
      downloadReport(auditId).catch((error: Error) =>
        toast.error(error.message),
      )
    else {
      setPendingDownload(true)
      generate.mutate(false)
    }
  }
  return (
    <section className="ai-report-panel" aria-label="AI 中文分析报告">
      <h3>AI 中文分析报告</h3>
      <p className="page-note">
        AI 汇总本项目 AI
        复审后的分类、判断依据、漏洞介绍、利用用例、关联源码和未完成范围。报告包含真实、误报与证据不足的候选，无需选择修复目标；复审结果变化后需要更新报告。
      </p>
      <div className="stage-row">
        <Button
          onClick={() => generate.mutate(Boolean(narrative))}
          disabled={!modelReady || busy}
        >
          {busy
            ? "正在生成中文报告…"
            : narrative
              ? "重新生成 AI 中文报告"
              : "生成 AI 中文报告"}
        </Button>
        <Button
          variant="outline"
          disabled={
            !modelReady || busy || report.isPending || Boolean(report.error)
          }
          onClick={exportMarkdown}
        >
          导出 Markdown 报告
        </Button>
        <Button
          variant="outline"
          onClick={() =>
            downloadReportJson(auditId).catch((error: Error) =>
              toast.error(error.message),
            )
          }
        >
          导出 JSON 报告
        </Button>
        <Button
          variant="outline"
          disabled={codeqlStatus(run) !== "completed"}
          onClick={() =>
            downloadSarif(auditId).catch((error: Error) =>
              toast.error(error.message),
            )
          }
        >
          <Download size={16} /> 下载 CodeQL SARIF
        </Button>
      </div>
      {!modelReady && (
        <p role="status">
          模型尚未配置，无法生成 AI 报告；JSON 原始记录仍可导出。
        </p>
      )}
      {ai?.status === "stale" && (
        <p role="status">
          审计判断或验证结果已变化，请更新 AI 中文报告后再导出。
        </p>
      )}
      {report.error && <p role="alert">报告读取失败：{report.error.message}</p>}
      {ai?.error && (
        <p role="alert">
          报告生成失败：{ai.error}。原有源码与人工判断保留，可重新生成。
        </p>
      )}
      {generate.error && <p role="alert">{generate.error.message}</p>}
      {narrative ? (
        <ReportWorkspace
          key={`${auditId}:${ai?.stage_id ?? "current"}`}
          narrative={narrative}
          candidates={candidates}
          evidence={report.data?.evidence ?? []}
          summary={report.data?.summary}
          model={ai?.model}
          createdAt={ai?.created_at}
        />
      ) : (
        !busy &&
        !report.isPending && (
          <p className="page-note">
            尚无与当前结果匹配的 AI
            中文报告。点击生成后，这里将展示具体分析和修复建议。
          </p>
        )
      )}
    </section>
  )
}
