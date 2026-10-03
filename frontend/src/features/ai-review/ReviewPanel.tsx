import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import type { AuditRun } from "@/api/audits"
import {
  addEvidence,
  getCandidates,
  getEvidence,
  type StageRun,
  startStage,
} from "@/api/stages"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { StageHistory } from "@/features/stages/StageHistory"
import { CandidateCard } from "./CandidateCard"
export function ReviewPanel({
  run,
  stages,
  modelReady,
}: {
  run: AuditRun
  stages: StageRun[]
  modelReady: boolean
}) {
  const [paths, setPaths] = useState("")
  const [discover, setDiscover] = useState(true)
  const [steps, setSteps] = useState(8)
  const [findings, setFindings] = useState(run.findings.map((item) => item.id))
  const [file, setFile] = useState("")
  const [line, setLine] = useState(1)
  const cache = useQueryClient()
  const busy = stages.some((item) =>
    ["queued", "running"].includes(item.status),
  )
  const candidates = useQuery({
    queryKey: ["candidates", run.id],
    queryFn: () => getCandidates(run.id),
    refetchInterval: busy ? 3000 : false,
  })
  const evidence = useQuery({
    queryKey: ["evidence", run.id],
    queryFn: () => getEvidence(run.id),
    refetchInterval: busy ? 3000 : false,
  })
  const start = useMutation({
    mutationFn: () =>
      startStage(run.id, "review", {
        paths: paths
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
        finding_ids: findings,
        discover,
        max_steps: steps,
      }),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  const manual = useMutation({
    mutationFn: () => addEvidence(run.id, file, line),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <section className="stage-section">
      <h3>AI 复审与主动取证</h3>
      <p>
        从静态告警或安全操作锚点开始。AI
        判断是建议，确认和排除需要人工证据判断。
      </p>
      <div className="stage-form">
        <details>
          <summary>选择静态告警（未选择时复审范围内所有告警）</summary>
          {run.findings.map((item) => (
            <label
              className="stage-check"
              key={item.id}
              htmlFor={`review-${run.id}-${item.id}`}
            >
              <Checkbox
                id={`review-${run.id}-${item.id}`}
                checked={findings.includes(item.id)}
                onCheckedChange={(checked) =>
                  setFindings(
                    checked
                      ? [...findings, item.id]
                      : findings.filter((id) => id !== item.id),
                  )
                }
              />
              {item.rule} · {item.locations[0].file}:{item.locations[0].line}
            </label>
          ))}
        </details>
        <label>
          取证范围（每行一个快照内文件或目录，留空为整个快照）
          <textarea
            className="audit-textarea"
            value={paths}
            onChange={(event) => setPaths(event.target.value)}
            placeholder="src/"
          />
        </label>
        <label className="stage-check" htmlFor={`discover-${run.id}`}>
          <Checkbox
            id={`discover-${run.id}`}
            checked={discover}
            onCheckedChange={(checked) => setDiscover(Boolean(checked))}
          />
          允许提出补充发现
        </label>
        <label htmlFor={`steps-${run.id}`}>
          最大模型推理步数
          <Input
            id={`steps-${run.id}`}
            type="number"
            min={1}
            max={16}
            value={steps}
            onChange={(event) => setSteps(Number(event.target.value))}
          />
        </label>
        <Button
          disabled={
            !modelReady || run.status !== "completed" || busy || start.isPending
          }
          onClick={() => start.mutate()}
        >
          启动 AI 复审
        </Button>
        {!modelReady ? (
          <p role="status">
            先在服务器 .env 配置模型服务，平台不会使用模拟结果。
          </p>
        ) : null}
      </div>
      <details>
        <summary>人工补充源码证据</summary>
        <div className="stage-form">
          <label htmlFor={`manual-file-${run.id}`}>
            快照文件路径
            <Input
              id={`manual-file-${run.id}`}
              value={file}
              onChange={(event) => setFile(event.target.value)}
            />
          </label>
          <label htmlFor={`manual-line-${run.id}`}>
            目标行
            <Input
              id={`manual-line-${run.id}`}
              type="number"
              min={1}
              value={line}
              onChange={(event) => setLine(Number(event.target.value))}
            />
          </label>
          <Button
            variant="outline"
            disabled={!file || manual.isPending}
            onClick={() => manual.mutate()}
          >
            读取并保存证据
          </Button>
        </div>
      </details>
      {candidates.error || evidence.error ? (
        <p role="alert">
          {candidates.error?.message ?? evidence.error?.message}
        </p>
      ) : null}
      {candidates.data?.map((candidate) => (
        <CandidateCard
          key={`${candidate.id}:${candidate.status}`}
          candidate={candidate}
          evidence={evidence.data ?? []}
          busy={busy}
        />
      ))}
      <StageHistory stages={stages} />
    </section>
  )
}
