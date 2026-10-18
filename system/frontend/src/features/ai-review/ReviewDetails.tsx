import { useState } from "react"
import type { AuditRun } from "@/api/audits"
import type { Candidate, StageRun } from "@/api/stages"
import { StageHistory } from "@/features/stages/StageHistory"
import { DiscoveryCoverage } from "./DiscoveryCoverage"

export function ReviewDetails({
  run,
  stages,
  candidates,
}: {
  run: AuditRun
  stages: StageRun[]
  candidates: Candidate[]
}) {
  const [diagnosticsOpened, setDiagnosticsOpened] = useState(false)
  const ordered = [...stages].sort((a, b) =>
    (b.created_at ?? "").localeCompare(a.created_at ?? ""),
  )
  const reviews = ordered.filter((item) => item.kind === "review")
  const latest = reviews[0]
  const older = ordered.filter((item) => item.id !== latest?.id)
  const result = latest?.result ?? {}
  const total = Array.isArray(result.candidate_ids)
    ? result.candidate_ids.length
    : null
  const remaining = Array.isArray(result.unreviewed_candidate_ids)
    ? result.unreviewed_candidate_ids.length
    : null
  const labels: Record<string, string> = {
    completed: "复核完成",
    awaiting_confirmation: "复核结果已生成",
    running: "正在复核",
    queued: "等待复核",
    failed: "本次复核失败",
    cancelled: "本次复核已取消",
  }
  const incompleteDiscovery = Boolean(
    run.coverage.dual_engine && run.coverage.dual_engine.status !== "completed",
  )
  return (
    <div className="review-footer">
      <div className="review-completion" role="status">
        <strong>
          {latest
            ? (labels[latest.status] ?? "复核状态待核实")
            : "尚未开始复核"}
        </strong>
        {total !== null && remaining !== null ? (
          <span>
            原始发现已处理 {Math.max(0, total - remaining)} / {total} 条 ·{" "}
            {remaining ? `${remaining} 项尚未复核` : "本轮候选无遗漏"}
          </span>
        ) : null}
        {latest?.status === "failed" ? (
          <span>可在下方重试，已有结果保留。</span>
        ) : null}
      </div>
      {incompleteDiscovery ? (
        <p className="page-note">
          初步审计仍有范围未检查，当前复核结果仅覆盖已提交的候选。可在审计发现页继续补审。
        </p>
      ) : null}
      {latest ? <StageHistory stages={[latest]} title="最近执行" /> : null}
      {older.length ? (
        <details className="review-footer-disclosure">
          <summary>更早的执行记录（{older.length}）</summary>
          <StageHistory stages={older} />
        </details>
      ) : null}
      <details
        className="review-footer-disclosure"
        onToggle={(event) => {
          if (event.currentTarget.open) setDiagnosticsOpened(true)
        }}
      >
        <summary>高级诊断</summary>
        {diagnosticsOpened ? (
          <div>
            <details>
              <summary>扫描覆盖与未完成范围</summary>
              <DiscoveryCoverage run={run} stages={stages} />
            </details>
            <details>
              <summary>漏洞汇总与来源关联</summary>
              <pre className="source-code">
                {JSON.stringify(candidates, null, 2)}
              </pre>
            </details>
            <details>
              <summary>锚点评价与未评估记录</summary>
              {reviews.map((item) => (
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
              <summary>复核批次、前提与关联记录</summary>
              {reviews.map((item) => (
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
            </details>
          </div>
        ) : null}
      </details>
    </div>
  )
}
