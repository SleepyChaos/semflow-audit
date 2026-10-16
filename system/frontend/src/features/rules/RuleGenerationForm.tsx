import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import type { AuditRun } from "@/api/audits"
import {
  type Candidate,
  type Capabilities,
  getRuleHoldouts,
  startStage,
} from "@/api/stages"
import { Button } from "@/components/ui/button"

export function RuleGenerationForm({
  run,
  capabilities,
  busy,
  candidate,
}: {
  run: AuditRun
  capabilities?: Capabilities
  busy: boolean
  candidate?: Candidate
}) {
  const [holdout, setHoldout] = useState("")
  const cache = useQueryClient()
  const holdouts = useQuery({
    queryKey: ["rule-holdouts"],
    queryFn: getRuleHoldouts,
  })
  const available = (holdouts.data ?? []).filter(
    (row) =>
      row.language === run.language && row.purpose === "vulnerability_detector",
  )
  const selectedHoldout = available.find((row) => row.id === holdout)
  const start = useMutation({
    mutationFn: () =>
      startStage(run.id, "rule", {
        candidate_id: candidate!.id,
        requirement: `检测与「${candidate!.review?.detail?.title ?? candidate!.title}」相同的漏洞条件，依据原始源码和复核证据提炼规则，避免匹配正常行为。`,
        purpose: "vulnerability_detector",
        strategy: "auto",
        holdout_id: selectedHoldout?.id ?? null,
        source_paths: [],
      }),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <>
      <Button
        disabled={
          !candidate ||
          !capabilities?.model_configured ||
          busy ||
          start.isPending
        }
        onClick={() => start.mutate()}
      >
        {start.isPending ? "正在提交…" : "生成检测规则"}
      </Button>
      {available.length > 0 && (
        <label className="result-inline-setting">
          独立验收集
          <select
            className="native-select"
            aria-label="独立规则测试集"
            value={selectedHoldout?.id ?? ""}
            onChange={(e) => setHoldout(e.target.value)}
            disabled={busy}
          >
            <option value="">暂不选择，生成草稿</option>
            {available.map((row) => (
              <option key={row.id} value={row.id}>
                {row.operation} · {row.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
      )}
      {holdouts.error && (
        <p role="alert">验收集读取失败：{holdouts.error.message}</p>
      )}
      {start.error && <p role="alert">{start.error.message}</p>}
    </>
  )
}
