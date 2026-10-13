import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import type { AuditRun } from "@/api/audits"
import { getCandidates, type StageRun, startStage } from "@/api/stages"
import { Button } from "@/components/ui/button"
import { StageHistory } from "@/features/stages/StageHistory"
import { CandidateWorkspace } from "./CandidateWorkspace"
import { DiscoveryCoverage } from "./DiscoveryCoverage"
import { ReviewControls } from "./ReviewControls"
export function ReviewPanel({
  run,
  stages,
  modelReady,
}: {
  run: AuditRun
  stages: StageRun[]
  modelReady: boolean
}) {
  const cache = useQueryClient()
  const busy = stages.some((item) =>
    ["queued", "running"].includes(item.status),
  )
  const ready =
    run.status === "completed" ||
    (run.status === "failed" && Boolean(run.coverage.dual_engine?.review_ready))
  const candidates = useQuery({
    queryKey: ["candidates", run.id],
    queryFn: () => getCandidates(run.id),
    refetchInterval: (query) =>
      busy ||
      query.state.data?.some((candidate) => candidate.localization_pending)
        ? 3000
        : false,
  })
  const start = useMutation({
    mutationFn: () =>
      startStage(run.id, "review", {
        finding_ids: run.findings.map((finding) => finding.id),
        discover: true,
        include_scout: true,
        max_steps: 8,
      }),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <section className="stage-section">
      <ReviewControls
        disabled={!modelReady || !ready || busy}
        pending={start.isPending}
        onStart={() => start.mutate()}
        reason={
          !modelReady
            ? "模型服务尚未配置，请查看执行环境。"
            : !ready
              ? "等待扫描就绪后可启动复核。"
              : busy
                ? "当前阶段正在执行，请等待或取消。"
                : null
        }
      />
      {candidates.data?.some((candidate) => candidate.localization_pending) ? (
        <p role="status">正在将历史英文说明转为中文，分类和源码保持原样…</p>
      ) : null}
      {candidates.data?.find((candidate) => candidate.localization_error)
        ?.localization_error ? (
        <p role="alert">
          中文说明生成失败：
          {
            candidates.data.find((candidate) => candidate.localization_error)
              ?.localization_error
          }
        </p>
      ) : null}
      {candidates.error ? <p role="alert">{candidates.error.message}</p> : null}
      {candidates.isPending ? (
        <p role="status">正在读取候选与证据…</p>
      ) : !candidates.error ? (
        <CandidateWorkspace candidates={candidates.data ?? []} busy={busy} />
      ) : (
        <Button
          variant="outline"
          onClick={() => {
            candidates.refetch()
          }}
        >
          重新读取候选与证据
        </Button>
      )}{" "}
      <details>
        <summary>扫描与粗筛覆盖详情</summary>
        <DiscoveryCoverage run={run} stages={stages} />
      </details>
      <details>
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
