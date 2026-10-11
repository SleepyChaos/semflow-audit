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
import { CandidateWorkspace } from "./CandidateWorkspace"
import { ReviewControls } from "./ReviewControls"
import { DiscoveryCoverage } from "./DiscoveryCoverage"
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
  const [includeScout, setIncludeScout] = useState(true)
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
        include_scout: includeScout,
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
  const scout = useMutation({
    mutationFn: () =>
      startStage(run.id, "scout", {
        paths: paths
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
      }),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  const ready =
    run.status === "completed" ||
    (run.status === "failed" && Boolean(run.coverage.dual_engine?.review_ready))
  return (
    <section className="stage-section">
      <ReviewControls disabled={!modelReady || !ready || busy} pending={start.isPending} onStart={() => start.mutate()} reason={!modelReady ? "模型服务尚未配置，请查看执行环境。" : !ready ? "等待扫描就绪后可启动复核。" : busy ? "当前阶段正在执行，请等待或取消。" : null}>      <div className="stage-form">
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
        <label className="stage-check" htmlFor={`scout-input-${run.id}`}>
          <Checkbox
            id={`scout-input-${run.id}`}
            checked={includeScout}
            onCheckedChange={(checked) => setIncludeScout(Boolean(checked))}
          />
          纳入独立粗筛候选
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
          variant="outline"
          disabled={!modelReady || !ready || busy || scout.isPending}
          onClick={() => scout.mutate()}
        >
          单独重新粗筛
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
      </ReviewControls>
      <DiscoveryCoverage run={run} stages={stages} />
      {candidates.error || evidence.error ? (
        <p role="alert">
          {candidates.error?.message ?? evidence.error?.message}
        </p>
      ) : null}
      <p className="page-note">
        相同候选身份展示一张卡片，优先保留人工决定；不同假设仍分别展示。
        原始粗筛和历次复核记录保存在下方历史中。
      </p>
      {candidates.isPending || evidence.isPending ? <p role="status">正在读取候选与证据…</p> : !candidates.error && !evidence.error ? <CandidateWorkspace candidates={candidates.data ?? []} evidence={evidence.data ?? []} stages={stages} busy={busy} /> : <Button variant="outline" onClick={() => {candidates.refetch();evidence.refetch()}}>重新读取候选与证据</Button>}      <details>
        <summary>全部原始候选记录与复核历史（未删除或按根因合并）</summary>
        <pre className="source-code">
          {JSON.stringify(candidates.data ?? [], null, 2)}
        </pre>
      </details>
      <details>
        <summary>锚点评价与未评估范围（不计为新增漏洞）</summary>
        {stages
          .filter((item) => item.kind === "review")
          .map((item) => (
            <pre className="source-code" key={item.id}>
              {JSON.stringify(
                {
                  stage: item.id,
                  assessments: item.result.anchor_assessments ?? [],
                  unreviewed: item.result.unreviewed_anchor_ids ?? [],
                },
                null,
                2,
              )}
            </pre>
          ))}
      </details>
      <details>
        <summary>复核前提、未评估候选与根因关联建议</summary>
        {stages
          .filter((item) => item.kind === "review")
          .map((item) => (
            <pre className="source-code" key={item.id}>
              {JSON.stringify(
                {
                  stage: item.id,
                  coverage: item.result.coverage_status,
                  batches: item.result.batches,
                  root_relations: item.result.root_relations,
                  unreviewed: item.result.unreviewed_candidate_ids,
                },
                null,
                2,
              )}
            </pre>
          ))}
        <p>关联建议保留全部候选与触发路径，不自动减少已确认数量。</p>
      </details>
      <StageHistory stages={stages} />
    </section>
  )
}
