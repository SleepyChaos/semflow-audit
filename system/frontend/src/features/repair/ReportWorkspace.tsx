import { FileText } from "lucide-react"
import { useId, useMemo, useState } from "react"
import type { AuditReport, Candidate, Evidence } from "@/api/stages"
import { reviewVerdict } from "@/features/ai-review/review-status"
import { ReportIssueContext } from "./ReportIssueContext"

type Narrative = NonNullable<NonNullable<AuditReport["ai_report"]>["narrative"]>
const priority: Record<string, number> = {
  supported: 0,
  insufficient: 1,
  neutral: 1,
  excluded: 2,
}

function TextList({ items }: { items: string[] }) {
  return (
    <ul>
      {items.map((text, i) => (
        <li key={`${i}:${text}`}>{text}</li>
      ))}
    </ul>
  )
}

export function ReportWorkspace({
  narrative,
  candidates,
  evidence,
  summary,
  model,
  createdAt,
}: {
  narrative: Narrative
  candidates: Candidate[]
  evidence: Evidence[]
  summary: AuditReport["summary"]
  model?: string
  createdAt?: string
}) {
  const [selected, setSelected] = useState<string | null>(null)
  const detailId = useId()
  const candidateMap = useMemo(
    () => new Map(candidates.map((row) => [row.id, row])),
    [candidates],
  )
  const entries = useMemo(
    () =>
      narrative.issues
        .map((issue) => {
          const candidate = candidateMap.get(issue.candidate_id)
          return {
            issue,
            candidate,
            verdict: candidate
              ? reviewVerdict(candidate)
              : { tone: "neutral", label: "待复核" },
          }
        })
        .sort((a, b) => priority[a.verdict.tone] - priority[b.verdict.tone]),
    [narrative.issues, candidateMap],
  )
  const current = entries.find((row) => row.issue.candidate_id === selected)
  return (
    <section
      className="candidate-workspace report-workspace"
      aria-label="报告阅读工作区"
    >
      <aside className="candidate-rail report-rail" aria-label="报告目录">
        <div className="rail-heading">
          报告目录 <span>{entries.length} 项</span>
        </div>
        <button
          type="button"
          className="candidate-option report-global-option"
          aria-pressed={!current}
          aria-controls={detailId}
          onClick={() => setSelected(null)}
        >
          <span>
            <FileText size={17} aria-hidden="true" />
            全局报告
          </span>
          <small>总体结论 · 修复进展 · 后续建议</small>
        </button>
        <nav className="report-issue-list" aria-label="报告漏洞列表">
          {entries.map(({ issue, candidate, verdict }) => (
            <button
              type="button"
              className="candidate-option"
              key={issue.candidate_id}
              data-verdict={verdict.tone}
              aria-pressed={current?.issue.candidate_id === issue.candidate_id}
              aria-controls={detailId}
              onClick={() => setSelected(issue.candidate_id)}
            >
              <span>{issue.title}</span>
              <span
                className="review-verdict-badge"
                data-verdict={verdict.tone}
              >
                {verdict.label}
              </span>
              <small>
                {candidate?.weakness}
                {candidate?.weakness ? " · " : ""}
                {candidate?.location.file ?? "位置待核实"}
                {candidate?.location.line ? `:${candidate.location.line}` : ""}
              </small>
            </button>
          ))}
          {!entries.length && (
            <p className="page-note">
              本次报告没有漏洞候选，请查看全局结论和审计范围。
            </p>
          )}
        </nav>
      </aside>
      <section
        id={detailId}
        className="report-detail-scroll"
        aria-label={current ? "漏洞报告详情" : "全局报告详情"}
        key={current?.issue.candidate_id ?? "global"}
      >
        <div className="ai-report-body report-detail-body">
          {current ? (
            <>
              <header className="report-detail-heading">
                <p className="report-eyebrow">漏洞分析报告</p>
                <h3>{current.issue.title}</h3>
                <p className="page-note">
                  {current.candidate?.location.file ?? "位置待核实"}
                  {current.candidate?.location.line
                    ? `:${current.candidate.location.line}`
                    : ""}
                </p>
                <span
                  className="review-verdict-badge"
                  data-verdict={current.verdict.tone}
                >
                  {current.verdict.label}
                </span>
              </header>
              <section className="report-content-section">
                <h4>问题说明</h4>
                <p>{current.issue.explanation}</p>
              </section>
              <section className="report-content-section">
                <h4>影响与风险</h4>
                <p>{current.issue.impact}</p>
              </section>
              <section className="report-content-section">
                <h4>修复建议</h4>
                <TextList items={current.issue.fix_suggestions} />
              </section>
              <section className="report-content-section">
                <h4>验证建议</h4>
                <TextList items={current.issue.verification_suggestions} />
                <p className="page-note">
                  建议用例尚未执行，实际验证状态以保存的执行记录为准。
                </p>
              </section>
              <section className="report-content-section">
                <h4>复审依据与关联证据</h4>
                <ReportIssueContext
                  candidate={current.candidate}
                  evidence={evidence}
                />
                <details className="report-evidence-ids">
                  <summary>
                    证据引用（{current.issue.evidence_ids.length}）
                  </summary>
                  <TextList items={current.issue.evidence_ids} />
                </details>
              </section>
            </>
          ) : (
            <>
              <header className="report-detail-heading">
                <p className="report-eyebrow">审计结果总览</p>
                <h3>全局报告</h3>
                <p className="page-note">
                  {model ? `模型 ${model}` : "AI 中文分析报告"}
                  {createdAt
                    ? ` · ${new Date(createdAt).toLocaleString()}`
                    : ""}
                </p>
              </header>
              {summary?.candidate_states && (
                <section
                  className="rule-validation-grid report-statistics"
                  aria-label="报告分类统计"
                >
                  {[
                    ["confirmed", "确认真实"],
                    ["insufficient", "证据不足"],
                    ["excluded", "确认误报"],
                    ["pending", "待复核"],
                  ].map(([key, label]) => (
                    <div key={key}>
                      <span>{label}</span>
                      <strong>{summary.candidate_states[key] ?? 0}</strong>
                    </div>
                  ))}
                </section>
              )}
              <section className="report-content-section">
                <h4>总体审计结论</h4>
                <p>{narrative.overview}</p>
              </section>
              <section className="report-content-section">
                <h4>修复与验证进展</h4>
                <p>{narrative.repair_review}</p>
              </section>
              <section className="report-content-section">
                <h4>审计限制与待验证事项</h4>
                <TextList items={narrative.limitations} />
              </section>
              <section className="report-content-section">
                <h4>后续行动建议</h4>
                <TextList items={narrative.next_steps} />
              </section>
            </>
          )}
        </div>
      </section>
    </section>
  )
}
