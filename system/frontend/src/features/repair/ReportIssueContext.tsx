import type { Candidate, Evidence } from "@/api/stages"
import { reviewVerdict } from "@/features/ai-review/review-status"

export function ReportIssueContext({
  candidate,
  evidence,
}: {
  candidate: Candidate | undefined
  evidence: Evidence[]
}) {
  if (!candidate) return null
  const review = candidate.review
  const verdict = reviewVerdict(candidate)
  const example = review?.detail?.exploitation
  const ids = new Set(review?.evidence_ids ?? candidate.evidence_ids)
  const sources = evidence.filter((row) => ids.has(row.id))
  return (
    <div className="report-issue-context">
      <span className="review-verdict-badge" data-verdict={verdict.tone}>
        {candidate.classification?.source === "human" ? "人工调整" : "复审分类"}{" "}
        · {verdict.label}
      </span>
      {review?.reason ? <p>复审依据：{review.reason}</p> : null}
      {example ? (
        <details>
          <summary>项目利用用例与前提（未实际执行）</summary>
          <p>入口：{example.entrypoint || "尚未确定"}</p>
          {example.prerequisites.length ? (
            <ul>
              {example.prerequisites.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          ) : null}
          {example.steps.length ? (
            <ol>
              {example.steps.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ol>
          ) : null}
          {example.example ? (
            <pre className="source-code">{example.example}</pre>
          ) : null}
          {example.expected_result ? (
            <p>预期现象：{example.expected_result}</p>
          ) : null}
          <p className="page-note">
            这是源码支持的演示或待验证用例，不代表已成功利用。
          </p>
        </details>
      ) : null}
      {review &&
      (review.missing_premises.length || review.runtime_unknowns.length) ? (
        <details>
          <summary>尚未确认的前提</summary>
          <ul>
            {[...review.missing_premises, ...review.runtime_unknowns].map(
              (text, i) => (
                <li key={`${i}:${text}`}>{text}</li>
              ),
            )}
          </ul>
        </details>
      ) : null}
      {sources.length ? (
        <details>
          <summary>关联源码与证据（{sources.length}）</summary>
          {sources.map((row) => (
            <details key={row.id}>
              <summary>
                {String(row.reference.file ?? row.kind)}
                {typeof row.reference.start_line === "number"
                  ? ` · 第 ${row.reference.start_line} 行起`
                  : ""}
              </summary>
              <pre className="source-code">{row.content}</pre>
            </details>
          ))}
        </details>
      ) : null}
    </div>
  )
}
