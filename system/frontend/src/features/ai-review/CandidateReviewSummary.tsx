import type { Candidate } from "@/api/stages"
import { reviewVerdict } from "./review-status"

export function CandidateReviewSummary({
  candidate,
}: {
  candidate: Candidate
}) {
  const review = candidate.review
  const detail = review?.detail
  const verdict = reviewVerdict({ ...candidate, classification: undefined })
  const example = detail?.exploitation
  return (
    <div className="candidate-review-summary">
      <section
        className="review-verdict-panel"
        data-verdict={verdict.tone}
        aria-label="AI 复核结论"
      >
        <strong>AI 复核 · {verdict.label}</strong>
        <p>
          {review?.reason ??
            "此项来自初步审计，启动统一复核后会展示具体判断和依据。"}
        </p>
        {review && !review.evaluated && review.status !== "reviewing" ? (
          <p>本项尚未形成有效复核结论，不代表已经完成检查。</p>
        ) : null}
      </section>
      <section className="review-detail-section" aria-label="漏洞描述">
        <h4>漏洞描述与项目影响</h4>
        <p>{detail?.description ?? candidate.description}</p>
        {detail ? <p>{detail.impact}</p> : null}
        {review?.checked_premises.length ? (
          <>
            <h5>复核依据</h5>
            <ul>
              {review.checked_premises.map((text, index) => (
                <li key={index}>{text}</li>
              ))}
            </ul>
          </>
        ) : null}
        {review?.missing_premises.length ? (
          <>
            <h5>缺失条件</h5>
            <ul>
              {review.missing_premises.map((text, index) => (
                <li key={index}>{text}</li>
              ))}
            </ul>
          </>
        ) : null}
        {review?.runtime_unknowns.length ? (
          <details>
            <summary>运行环境待核实条件</summary>
            <ul>
              {review.runtime_unknowns.map((text, index) => (
                <li key={index}>{text}</li>
              ))}
            </ul>
          </details>
        ) : null}
      </section>
      <section className="review-detail-section" aria-label="项目利用用例">
        <h4>
          {example?.status === "blocked"
            ? "利用场景与阻断依据"
            : "基于本项目的利用用例"}
        </h4>
        {example ? (
          <>
            <p className="page-note">
              源码推导示例 · 未执行验证
              {example.status === "missing_preconditions"
                ? " · 利用前提尚不完整"
                : ""}
            </p>
            {example.entrypoint ? (
              <p>
                <strong>项目入口：</strong>
                {example.entrypoint}
              </p>
            ) : null}
            {example.prerequisites.length ? (
              <>
                <h5>利用前提</h5>
                <ul>
                  {example.prerequisites.map((text, index) => (
                    <li key={index}>{text}</li>
                  ))}
                </ul>
              </>
            ) : null}
            {example.steps.length ? (
              <ol>
                {example.steps.map((text, index) => (
                  <li key={index}>{text}</li>
                ))}
              </ol>
            ) : null}
            {example.example ? (
              <pre className="source-code">
                <code>{example.example}</code>
              </pre>
            ) : null}
            <p>
              <strong>
                {example.status === "blocked"
                  ? "阻断依据："
                  : "预期现象与限制："}
              </strong>
              {example.expected_result}
            </p>
          </>
        ) : (
          <p className="page-note">
            {review
              ? "这条历史复核尚未生成项目利用用例。重新启动统一复核后，新结果会包含源码支持的用例或缺失前提。"
              : "完成统一复核后展示项目利用用例；当前尚未生成。"}
          </p>
        )}
      </section>
    </div>
  )
}
