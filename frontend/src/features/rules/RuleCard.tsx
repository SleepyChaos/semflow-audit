import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import {
  approveFixtures,
  downloadQuery,
  publishRule,
  type RuleVersion,
  retireRule,
} from "@/api/stages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ProjectReplayReview } from "./ProjectReplayReview"
export function RuleCard({
  rule,
  awaiting,
}: {
  rule: RuleVersion
  awaiting: boolean
}) {
  const [reason, setReason] = useState("")
  const cache = useQueryClient()
  const action = useMutation({
    mutationFn: (kind: string) =>
      kind === "approve"
        ? approveFixtures(rule.id, reason)
        : kind === "publish"
          ? publishRule(rule.id)
          : retireRule(rule.id),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <article className="candidate-card">
      <header>
        <h4>{rule.title}</h4>
        <Badge variant="outline">{rule.status}</Badge>
      </header>
      <p>
        用途 {rule.purpose} · 策略 {rule.strategy} · 版本 {rule.id}
      </p>
      <details>
        <summary>查询与模型模块</summary>
        <pre className="source-code">{rule.query}</pre>
        {Object.entries(rule.modules).map(([name, content]) => (
          <pre className="source-code" key={name}>
            {`${name}\n${content}`}
          </pre>
        ))}
      </details>
      <details>
        <summary>RAG 检索引用</summary>
        {rule.retrieval.map((item) => (
          <article key={item.id}>
            <h4>{item.title}</h4>
            <p>
              {item.source} · {item.version.slice(0, 16)}
            </p>
            <pre className="source-code">{item.content}</pre>
          </article>
        ))}
      </details>
      <details>
        <summary>正反例与预期位置（需要核实覆盖与语义）</summary>
        <pre className="source-code">
          {JSON.stringify(rule.fixtures, null, 2)}
        </pre>
      </details>
      <p>
        独立测试集：{rule.holdout_id ?? "未选择"}
        。自生成样本通过与独立验收分别记录。
      </p>
      <details>
        <summary>规则验收与覆盖分析</summary>
        <pre className="source-code">
          {JSON.stringify(rule.validation, null, 2)}
        </pre>
      </details>
      <ProjectReplayReview rule={rule} />
      {awaiting && !rule.fixtures_approved ? (
        <div className="stage-form">
          <label>
            样本确认理由
            <textarea
              className="audit-textarea"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <Button
            disabled={reason.length < 10 || action.isPending}
            onClick={() => action.mutate("approve")}
          >
            批准样本并运行真实验收
          </Button>
        </div>
      ) : null}
      <div className="stage-row">
        <Button
          variant="outline"
          onClick={() =>
            downloadQuery(rule.id).catch((error: Error) =>
              toast.error(error.message),
            )
          }
        >
          下载查询
        </Button>
        {rule.status === "validated" ? (
          <Button
            disabled={action.isPending}
            onClick={() => action.mutate("publish")}
          >
            发布此版本
          </Button>
        ) : null}
        {rule.status === "published" ? (
          <Button
            variant="outline"
            disabled={action.isPending}
            onClick={() => action.mutate("retire")}
          >
            停用此版本
          </Button>
        ) : null}
      </div>
      <p>样本通过不代表真实项目准确率；新扫描需显式选择发布版本。</p>
    </article>
  )
}
