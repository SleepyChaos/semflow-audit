import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import {
  type Candidate,
  decideCandidate,
  type Evidence,
  getDecisions,
} from "@/api/stages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
export function CandidateCard({
  candidate,
  evidence,
  busy,
}: {
  candidate: Candidate
  evidence: Evidence[]
  busy: boolean
}) {
  const [reason, setReason] = useState("")
  const [status, setStatus] = useState("confirmed")
  const [ids, setIds] = useState(candidate.evidence_ids)
  const [history, setHistory] = useState(false)
  const cache = useQueryClient()
  const decisions = useQuery({
    queryKey: ["decisions", candidate.id],
    queryFn: () => getDecisions(candidate.id),
    enabled: history,
  })
  const mutation = useMutation({
    mutationFn: () =>
      decideCandidate(candidate.id, { status, reason, evidence_ids: ids }),
    onSuccess: async () => {
      await cache.invalidateQueries()
      setReason("")
      toast.success("人工判断已记录")
    },
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <article className="candidate-card">
      <header>
        <h4>{candidate.title}</h4>
        <Badge variant="outline">{candidate.status}</Badge>
      </header>
      <p>{candidate.description}</p>
      <p>
        弱点：{candidate.weakness} · 模型建议：{candidate.model_assessment} ·
        人工状态：{candidate.status}
      </p>
      <p className="text-sm text-muted-foreground">
        来源：{candidate.origin === "ai" ? "AI 补充候选" : "原始静态告警"} ·
        仅人工确认计入已确认发现
      </p>
      <details>
        <summary>选择判断依据（源码或查询证据必选）</summary>
        {evidence.map((item) => (
          <div key={item.id} className="evidence-choice">
            <label htmlFor={`candidate-${candidate.id}-${item.id}`}>
              <Checkbox
                id={`candidate-${candidate.id}-${item.id}`}
                checked={ids.includes(item.id)}
                onCheckedChange={(checked) =>
                  setIds(
                    checked
                      ? [...ids, item.id]
                      : ids.filter((id) => id !== item.id),
                  )
                }
              />
              <span>
                {item.kind} ·{" "}
                {String(
                  item.reference.file ?? item.reference.rule_version ?? item.id,
                )}
              </span>
            </label>
            <details>
              <summary>证据内容</summary>
              <pre className="source-code">{item.content}</pre>
              <p className="text-xs">
                快照 {item.snapshot_hash.slice(0, 16)} · SHA256{" "}
                {item.digest.slice(0, 16)}
              </p>
            </details>
          </div>
        ))}
      </details>
      <div className="stage-form">
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger aria-label="人工判断状态">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="confirmed">已确认</SelectItem>
            <SelectItem value="excluded">支持排除</SelectItem>
            <SelectItem value="pending">待确认</SelectItem>
            <SelectItem value="insufficient">证据不足</SelectItem>
          </SelectContent>
        </Select>
        <label>
          判断理由（至少 10 个字符）
          <textarea
            className="audit-textarea"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            maxLength={4000}
          />
        </label>
        <Button
          disabled={busy || mutation.isPending || reason.length < 10}
          onClick={() => mutation.mutate()}
        >
          记录人工判断
        </Button>
      </div>
      <Button variant="ghost" size="sm" onClick={() => setHistory(!history)}>
        判断历史
      </Button>
      {history ? (
        <pre className="source-code">
          {JSON.stringify(decisions.data ?? [], null, 2)}
        </pre>
      ) : null}
    </article>
  )
}
