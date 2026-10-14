import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { acceptRepair, downloadDiff, type RepairRecord } from "@/api/stages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { labelStatus } from "@/features/stages/stage-labels"
import { RepairComparison } from "./RepairComparison"
import { RepairDiff } from "./RepairDiff"
import { ValidationSummary } from "./ValidationSummary"
export function RepairCard({
  record,
  suiteId = "",
  busy = false,
}: {
  record: RepairRecord
  suiteId?: string
  busy?: boolean
}) {
  const [reason, setReason] = useState("")
  const [reviewedStage, setReviewedStage] = useState("")
  const proofId = `${record.comparison?.stage_id ?? ""}:${record.comparison?.receipt_hash ?? ""}`
  const reviewed =
    reviewedStage === proofId && Boolean(record.comparison?.stage_id)
  const cache = useQueryClient()
  const accept = useMutation({
    mutationFn: () =>
      acceptRepair(record.id, reason, record.comparison?.stage_id, reviewed),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <article className="candidate-card repair-result">
      <header>
        <h3>
          修复补丁 · {new Set(record.changes.map((change) => change.file)).size}{" "}
          个文件
        </h3>
        <Badge variant="outline">
          {record.acceptance_ready && record.status !== "accepted"
            ? "前后对比通过，待人工接受"
            : record.status === "accepted"
              ? "已人工接受"
              : labelStatus(record.status)}
        </Badge>
      </header>
      <p className="page-note">
        Diff：{record.changes.length} 个修改 · 人工接受：
        {record.acceptance_reason ? "已记录" : "尚未接受"}
      </p>
      <RepairDiff record={record} />
      {record.validation_summary ? (
        <ValidationSummary checks={record.validation_summary} />
      ) : (
        <p className="page-note">
          原始验证结果保存在技术详情中；通过已有检查不代表全部业务和漏洞测试都已通过。
        </p>
      )}
      <RepairComparison
        id={record.id}
        comparison={record.comparison}
        suiteId={suiteId}
        busy={busy}
        accepted={record.status === "accepted"}
      />
      <details>
        <summary>验证结果（技术详情）</summary>
        <pre className="source-code">
          {JSON.stringify(record.validation, null, 2)}
        </pre>
      </details>
      {accept.error ? (
        <p role="alert">接受失败：{accept.error.message}</p>
      ) : null}
      <Button
        variant="outline"
        onClick={() =>
          downloadDiff(record.id).catch((error: Error) =>
            toast.error(error.message),
          )
        }
      >
        下载 Diff
      </Button>
      {record.acceptance_ready && record.status !== "accepted" ? (
        <div className="stage-form">
          <label>
            补丁审阅理由
            <textarea
              className="audit-textarea"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <label className="stage-check" htmlFor={`review-tests-${record.id}`}>
            <Checkbox
              id={`review-tests-${record.id}`}
              aria-label="已审阅测试断言和前后结果"
              checked={reviewed}
              onCheckedChange={(value) =>
                setReviewedStage(value === true ? proofId : "")
              }
            />
            <span>我已核对测试断言、前后结果和补丁，认可所列测试范围。</span>
          </label>
          <Button
            disabled={
              !reviewed || reason.length < 10 || accept.isPending || busy
            }
            onClick={() => accept.mutate()}
          >
            接受此补丁
          </Button>
        </div>
      ) : null}
      <p>接受和下载不会改写原始快照，请自行审阅并应用补丁。</p>
    </article>
  )
}
