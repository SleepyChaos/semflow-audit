import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { toast } from "sonner"
import {
  downloadReport,
  downloadReportJson,
  getReport,
  startReport,
} from "@/api/stages"
import { Button } from "@/components/ui/button"

export function AIReportPanel({
  auditId,
  modelReady,
}: {
  auditId: string
  modelReady: boolean
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
        AI
        根据本项目源码证据和检查记录，解释问题位置、风险、修复建议及验证边界。第一次导出会先生成，结果变化后需要更新。
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
        <div className="ai-report-body">
          <p className="page-note">
            由模型 {ai?.model} 生成 ·{" "}
            {ai?.created_at ? new Date(ai.created_at).toLocaleString() : ""}
            。以下是 AI 建议，人工状态和执行结果单独记录。
          </p>
          <h4>这个项目发现了什么</h4>
          <p>{narrative.overview}</p>
          {narrative.issues.map((issue) => {
            const candidate = candidates.find(
              (row) => row.id === issue.candidate_id,
            )
            return (
              <article className="reader-explanation" key={issue.candidate_id}>
                <h4>{issue.title}</h4>
                <p>
                  位置：{candidate?.location.file ?? "位置待核实"}
                  {candidate?.location.line
                    ? `:${candidate.location.line}`
                    : ""}
                </p>
                <dl>
                  <div>
                    <dt>这里发生了什么</dt>
                    <dd>{issue.explanation}</dd>
                  </div>
                  <div>
                    <dt>可能有什么影响</dt>
                    <dd>{issue.impact}</dd>
                  </div>
                  <div>
                    <dt>AI 修复建议</dt>
                    <dd>
                      <ul>
                        {issue.fix_suggestions.map((text, i) => (
                          <li key={`${i}:${text}`}>{text}</li>
                        ))}
                      </ul>
                    </dd>
                  </div>
                  <div>
                    <dt>建议如何验证</dt>
                    <dd>
                      <ul>
                        {issue.verification_suggestions.map((text, i) => (
                          <li key={`${i}:${text}`}>{text}</li>
                        ))}
                      </ul>
                    </dd>
                  </div>
                </dl>
                <p className="reader-boundary">
                  建议的测试不代表已经执行；源码证据 ID：
                  {issue.evidence_ids.join("、") || "暂无，需要补证据"}
                </p>
              </article>
            )
          })}
          <h4>修复与验证到哪一步</h4>
          <p>{narrative.repair_review}</p>
          <h4>还有哪些不确定</h4>
          <ul>
            {narrative.limitations.map((text, i) => (
              <li key={`${i}:${text}`}>{text}</li>
            ))}
          </ul>
          <h4>下一步怎么做</h4>
          <ul>
            {narrative.next_steps.map((text, i) => (
              <li key={`${i}:${text}`}>{text}</li>
            ))}
          </ul>
        </div>
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
