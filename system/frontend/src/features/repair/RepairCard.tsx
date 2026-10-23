import type { RepairRecord } from "@/api/stages"
import { Badge } from "@/components/ui/badge"
import { RepairDiff } from "./RepairDiff"
import { RepairTestEvidence } from "./RepairTestEvidence"

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
          {record.status === "accepted" ? "已人工接受" : "补丁已生成"}
        </Badge>
      </header>
      <RepairTestEvidence auditId={auditId} record={record} />
      <RepairDiff record={record} />
      <p className="page-note">
        下载 Diff 不会改写原始源码，可在原项目中查看并应用补丁。
      </p>
    </article>
  )
}
