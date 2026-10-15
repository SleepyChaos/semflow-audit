import type { RepairRecord } from "@/api/stages"
import { Badge } from "@/components/ui/badge"
import { labelStatus } from "@/features/stages/stage-labels"
import { RepairComparison } from "./RepairComparison"
import { RepairDiff } from "./RepairDiff"
import { RepairTestEvidence } from "./RepairTestEvidence"
import { ValidationSummary } from "./ValidationSummary"

export function RepairCard({
  record,
  auditId,
}: {
  record: RepairRecord
  auditId: string
}) {
  return (
    <article className="candidate-card repair-result">
      <header>
        <h3>
          修复补丁 · {new Set(record.changes.map((change) => change.file)).size}{" "}
          个文件
        </h3>
        <Badge variant="outline">
          {record.acceptance_ready && record.status !== "accepted"
            ? "前后对比通过，待接受"
            : record.status === "accepted"
              ? "已人工接受"
              : record.status === "checks_passed"
                ? "已有检查通过"
                : labelStatus(record.status)}
        </Badge>
      </header>
      {record.validation_summary && (
        <ValidationSummary checks={record.validation_summary} />
      )}
      <RepairComparison
        id={record.id}
        comparison={record.comparison}
        suiteId=""
        busy={false}
        accepted={record.status === "accepted"}
        readOnly
      />
      <RepairTestEvidence auditId={auditId} record={record} />
      <RepairDiff record={record} />
      <details>
        <summary>验证结果（技术详情）</summary>
        <pre className="source-code">
          {JSON.stringify(record.validation, null, 2)}
        </pre>
      </details>
      <p className="page-note">
        下载和接受不会改写原始快照；接受补丁表示已审阅当前
        Diff、测试断言和前后验证结果。
      </p>
    </article>
  )
}
