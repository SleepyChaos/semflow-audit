import type { ValidationCheck } from "@/api/stages"

export function ValidationSummary({ checks }: { checks: ValidationCheck[] }) {
  return (
    <section className="validation-summary" aria-label="验证结论与下一步">
      <h4>这次验证说明了什么</h4>
      <p className="page-note">
        每项检查的范围不同。通过已有检查，仍需要核对未执行的功能和漏洞测试。
      </p>
      <dl>
        {checks.map((check) => (
          <div className="validation-check" key={check.label}>
            <dt>
              <strong>{check.label}</strong>
              <span>{check.status}</span>
            </dt>
            <dd>
              <p>{check.description}</p>
              <p className="reader-next-step">{check.next_step}</p>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
