import { useQuery } from "@tanstack/react-query"
import type { RepairRecord } from "@/api/stages"
import { getVerificationSuites } from "@/api/verification"

export function RepairTestEvidence({
  auditId,
  record,
}: {
  auditId: string
  record: RepairRecord
}) {
  const suites = useQuery({
    queryKey: ["verification-suites", auditId],
    queryFn: () => getVerificationSuites(auditId),
  })
  const suite =
    suites.data?.find(
      (row) => row.id === record.comparison?.identity?.suite_id,
    ) ??
    suites.data?.find((row) =>
      record.candidate_ids.every((id) => row.candidate_ids.includes(id)),
    )
  if (!suite) return null
  return (
    <details className="repair-test-evidence">
      <summary>验收测试用例与代码 · {suite.suite.title}</summary>
      <p>{suite.suite.summary}</p>
      <ul>
        {suite.suite.cases.map((test) => (
          <li key={test.name}>
            <strong>{test.category === "security" ? "安全" : "功能"}：</strong>
            {test.input_description} → {test.expected_behavior}
          </li>
        ))}
      </ul>
      {suite.suite.assumptions.length > 0 && (
        <>
          <h4>待核实前提</h4>
          <ul>
            {suite.suite.assumptions.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </>
      )}
      <p className="page-note">
        镜像：{suite.image}；生成测试不代表测试已执行。
      </p>
      {Object.entries(suite.suite.files).map(([name, code]) => (
        <details key={name}>
          <summary>{name}</summary>
          <pre className="source-code">{code}</pre>
        </details>
      ))}
    </details>
  )
}
