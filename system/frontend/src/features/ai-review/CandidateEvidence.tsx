import { useQuery } from "@tanstack/react-query"
import { getCandidateEvidence } from "@/api/review"
import type { Candidate } from "@/api/stages"
import { Button } from "@/components/ui/button"

export function CandidateEvidence({
  candidate,
  busy,
}: {
  candidate: Candidate
  busy: boolean
}) {
  const evidence = useQuery({
    queryKey: [
      "candidate-evidence",
      candidate.id,
      candidate.evidence_ids.join(","),
    ],
    queryFn: () => getCandidateEvidence(candidate.id),
    refetchInterval: busy ? 3000 : false,
  })
  return (
    <section className="review-detail-section" aria-label="本漏洞关联源码">
      <h4>本漏洞关联源码</h4>
      <p className="page-note">AI 自动关联本漏洞的源码证据，可按需展开查看。</p>
      {evidence.isPending ? (
        <p role="status">正在读取关联源码…</p>
      ) : evidence.error ? (
        <div role="alert">
          <p>读取失败：{evidence.error.message}</p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => evidence.refetch()}
          >
            重新读取
          </Button>
        </div>
      ) : !evidence.data?.length ? (
        <p>当前没有已保存的关联源码。</p>
      ) : (
        evidence.data.map((item) => (
          <details
            className="evidence-choice evidence-source-disclosure"
            key={item.id}
          >
            <summary>
              {String(
                item.reference.file ??
                  item.reference.rule_version ??
                  "关联证据",
              )}
              {typeof item.reference.start_line === "number"
                ? ` · 第 ${item.reference.start_line}–${item.reference.end_line} 行`
                : ""}
            </summary>
            <pre className="source-code">
              <code>{item.content}</code>
            </pre>
            <p className="evidence-digest">
              快照 {item.snapshot_hash.slice(0, 16)} · SHA256{" "}
              {item.digest.slice(0, 16)}
            </p>
          </details>
        ))
      )}
    </section>
  )
}
