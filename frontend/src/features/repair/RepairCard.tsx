import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { acceptRepair, downloadDiff, type RepairRecord } from "@/api/stages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { labelStatus } from "@/features/stages/stage-labels"
import { ValidationSummary } from "./ValidationSummary"
export function RepairCard({ record }: { record: RepairRecord }) {
  const [reason, setReason] = useState("")
  const cache = useQueryClient()
  const accept = useMutation({
    mutationFn: () => acceptRepair(record.id, reason),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <article className="candidate-card">
      <header>
        <h4>修复尝试 {record.id.slice(0, 8)}</h4>
        <Badge variant="outline">
          {record.status === "checks_passed"
            ? "验证通过，待人工接受"
            : record.status === "accepted"
              ? "已人工接受"
              : labelStatus(record.status)}
        </Badge>
      </header>
      <p className="page-note">
        Diff：{record.changes.length} 个修改 · 人工接受：
        {record.acceptance_reason ? "已记录" : "尚未接受"}
      </p>
      {record.validation_summary ? (
        <ValidationSummary checks={record.validation_summary} />
      ) : (
        <p className="page-note">
          原始验证结果保存在技术详情中；通过已有检查不代表全部业务和漏洞测试都已通过。
        </p>
      )}
      {record.changes.map((change, index) => (
        <details key={`${change.file}:${index}`}>
          <summary>{change.file} · 查看具体改动</summary>
          <p>{change.reason}</p>
          <pre className="source-code">
            {`--- 原文\n${change.old_text}\n+++ 新文\n${change.new_text}`}
          </pre>
        </details>
      ))}
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
      {record.status === "checks_passed" ? (
        <div className="stage-form">
          <label>
            补丁审阅理由
            <textarea
              className="audit-textarea"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <Button
            disabled={reason.length < 10 || accept.isPending}
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
