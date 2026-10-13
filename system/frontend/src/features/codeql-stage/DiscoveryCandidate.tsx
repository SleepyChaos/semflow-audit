import { useQuery } from "@tanstack/react-query"
import type { AuditRun } from "@/api/audits"
import { type Candidate, getEvidence } from "@/api/stages"
import { Button } from "@/components/ui/button"
import { humanStatuses } from "@/features/ai-review/CandidateWorkspace"

export function DiscoveryCandidate({
  candidate,
  run,
}: {
  candidate: Candidate
  run: AuditRun
}) {
  const evidence = useQuery({
    queryKey: ["evidence", run.id],
    queryFn: () => getEvidence(run.id),
    retry: 1,
    staleTime: 3000,
  })
  const linked =
    evidence.data?.filter(
      (item) =>
        item.stage_id === candidate.stage_id &&
        item.snapshot_hash === run.snapshot_hash &&
        candidate.evidence_ids.includes(item.id),
    ) ?? []
  return (
    <article className="discovery-candidate-detail" aria-label="AI 候选详情">
      <h4>{candidate.title}</h4>
      <p>{candidate.description}</p>
      <p className="page-note">
        {candidate.location.file ?? "位置待核实"}:
        {candidate.location.line ?? "—"}
        {" · "}
        {candidate.weakness}
        {" · "}
        {humanStatuses[candidate.status] ?? candidate.status}
      </p>
      <p className="page-note">
        初审提出的候选仍需复核；人工确认结果单独记录。
      </p>
      {evidence.isPending ? (
        <p role="status">正在读取关联证据…</p>
      ) : evidence.error ? (
        <div role="alert">
          <p>关联证据读取失败：{evidence.error.message}</p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => evidence.refetch()}
          >
            重新读取证据
          </Button>
        </div>
      ) : linked.length ? (
        linked.map((item) => (
          <div key={item.id}>
            <p className="page-note">
              关联证据 · {String(item.reference.file ?? item.kind)}
            </p>
            <pre className="source-code">
              <code>{item.content}</code>
            </pre>
          </div>
        ))
      ) : (
        <p role="status">暂未读取到属于此候选和源码快照的关联证据。</p>
      )}
    </article>
  )
}
