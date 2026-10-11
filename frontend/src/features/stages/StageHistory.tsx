import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import {
  cancelStage,
  getStageLogs,
  recoverStage,
  retryStage,
  type StageRun,
} from "@/api/stages"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { labelPhase, labelStatus } from "./stage-labels"
export function StageHistory({ stages }: { stages: StageRun[] }) {
  const [selected, setSelected] = useState<string | null>(null)
  const stage = stages.find((item) => item.id === selected)
  const cache = useQueryClient()
  const logs = useQuery({
    queryKey: ["stage-logs", selected],
    queryFn: () => getStageLogs(selected!),
    enabled: Boolean(selected),
    refetchInterval: stage?.status === "running" ? 3000 : false,
  })
  const action = useMutation({
    mutationFn: ({ id, kind }: { id: string; kind: string }) =>
      kind === "retry"
        ? retryStage(id)
        : kind === "recover"
          ? recoverStage(id)
          : cancelStage(id),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <section className="stage-history">
      <h3>执行历史</h3>
      {!stages.length ? (
        <p>尚未执行该阶段。</p>
      ) : (
        stages.map((item) => (
          <div key={item.id} className="stage-row">
            <Button variant="ghost" onClick={() => setSelected(item.id)}>
              {item.kind === "report" ? "AI 报告 · " : ""}
              {new Date(item.created_at).toLocaleString()} ·{" "}
              {labelPhase(item.phase)}
            </Button>
            <Badge variant="outline">{labelStatus(item.status)}</Badge>
            {["failed", "cancelled"].includes(item.status) ? (
              <Button
                size="sm"
                variant="outline"
                disabled={action.isPending}
                onClick={() => action.mutate({ id: item.id, kind: "retry" })}
              >
                新建重跑
              </Button>
            ) : null}
            {["queued", "running", "awaiting_confirmation"].includes(
              item.status,
            ) ? (
              <Button
                size="sm"
                variant="outline"
                disabled={action.isPending}
                onClick={() => action.mutate({ id: item.id, kind: "cancel" })}
              >
                取消
              </Button>
            ) : null}
            {item.status === "running" ? (
              <Button
                size="sm"
                variant="ghost"
                disabled={action.isPending}
                onClick={() => action.mutate({ id: item.id, kind: "recover" })}
              >
                标记失联
              </Button>
            ) : null}
          </div>
        ))
      )}
      {stage ? (
        <details open>
          <summary>执行详情 · {stage.model ?? "模型信息未记录"}</summary>
          <p>
            执行步骤：{stage.phase} · 原始状态：{stage.status}
            。执行完成表示本次任务结束，不代表安全检查全部通过。
          </p>
          {stage.error ? <p role="alert">{stage.error}</p> : null}
          <pre className="source-code">
            {JSON.stringify(
              {
                result: stage.result,
                usage: stage.usage,
                model_config: stage.model_config_snapshot,
                model_calls: stage.model_calls,
              },
              null,
              2,
            )}
          </pre>
          <pre className="source-code">
            {logs.data?.text ?? logs.error?.message ?? "暂无日志"}
          </pre>
        </details>
      ) : null}
    </section>
  )
}
