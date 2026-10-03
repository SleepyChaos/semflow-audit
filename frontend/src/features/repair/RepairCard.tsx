import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { acceptRepair, downloadDiff, type RepairRecord } from "@/api/stages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
        <Badge variant="outline">{record.status}</Badge>
      </header>
      {record.changes.map((change, index) => (
        <details key={`${change.file}:${index}`}>
          <summary>
            {change.file} · {change.reason}
          </summary>
          <pre className="source-code">
            {`--- 原文\n${change.old_text}\n+++ 新文\n${change.new_text}`}
          </pre>
        </details>
      ))}
      <details>
        <summary>验证结果</summary>
        <pre className="source-code">
          {JSON.stringify(record.validation, null, 2)}
        </pre>
      </details>
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
