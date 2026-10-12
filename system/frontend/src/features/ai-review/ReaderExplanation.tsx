import type { CandidateExplanation } from "@/api/stages"

export function ReaderExplanation({
  explanation,
}: {
  explanation: CandidateExplanation
}) {
  return (
    <section className="reader-explanation" aria-label="问题的中文导读">
      <div className="reader-location">
        <span>问题位置</span>
        <strong>{explanation.location}</strong>
      </div>
      <dl>
        <div>
          <dt>这里发生了什么</dt>
          <dd>{explanation.observation}</dd>
        </div>
        <div>
          <dt>这类问题的风险</dt>
          <dd>{explanation.risk}</dd>
        </div>
        <div>
          <dt>修复方向</dt>
          <dd>{explanation.remediation}</dd>
        </div>
        <div>
          <dt>你接下来要做什么</dt>
          <dd>{explanation.next_step}</dd>
        </div>
      </dl>
      <p className="reader-boundary">{explanation.boundary}</p>
    </section>
  )
}
