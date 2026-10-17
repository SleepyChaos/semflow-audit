import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { useId, useState } from "react"
import type { AuditRun } from "@/api/audits"
import {
  type Capabilities,
  getCandidates,
  getRules,
  type StageRun,
} from "@/api/stages"
import { WorkspaceSelect } from "@/components/WorkspaceSelect"
import { currentReviewCandidates } from "@/features/ai-review/review-status"
import { StageHistory } from "@/features/stages/StageHistory"
import { RuleActions } from "./RuleActions"
import { RuleCard } from "./RuleCard"
import { RuleGenerationForm } from "./RuleGenerationForm"

export function RulePanel({
  run,
  stages,
  capabilities,
}: {
  run: AuditRun
  stages: StageRun[]
  capabilities?: Capabilities
}) {
  const selectionId = useId()
  const [focused, setFocused] = useState("")
  const [versionId, setVersionId] = useState("")
  const busy = stages.some((row) => ["queued", "running"].includes(row.status))
  const candidates = useQuery({
    queryKey: ["candidates", run.id],
    queryFn: () => getCandidates(run.id),
  })
  const rules = useQuery({
    queryKey: ["rules", run.language],
    queryFn: () => getRules(run.language),
    refetchInterval: busy ? 2500 : false,
  })
  const confirmed = currentReviewCandidates(candidates.data ?? []).filter(
    (row) =>
      row.classification?.status === "confirmed" ||
      (!row.classification && row.status === "confirmed"),
  )
  const taskRules = (rules.data ?? [])
    .filter((row) => row.audit_id === run.id)
    .sort((a, b) => {
      const time = (id: string) =>
        stages.find((stage) => stage.id === id)?.created_at ?? ""
      return time(b.stage_id).localeCompare(time(a.stage_id))
    })
  const sourceId = (stageId: string) =>
    stages.find((row) => row.id === stageId)?.inputs.candidate_id
  const standalone = taskRules.filter(
    (row) => !confirmed.some((c) => c.id === sourceId(row.stage_id)),
  )
  const standaloneRule = standalone.find((row) => `rule:${row.id}` === focused)
  const current = standaloneRule
    ? undefined
    : (confirmed.find((row) => row.id === focused) ?? confirmed[0])
  const related = standaloneRule
    ? [standaloneRule]
    : taskRules.filter((row) => sourceId(row.stage_id) === current?.id)
  const rule = related.find((row) => row.id === versionId) ?? related[0]
  const latestStage = [...stages].sort((a, b) =>
    b.created_at.localeCompare(a.created_at),
  )[0]
  const awaiting = stages.some(
    (row) =>
      row.id === rule?.stage_id && row.status === "awaiting_confirmation",
  )
  return (
    <section className="stage-section downstream-workspace">
      <section
        className="action-banner result-controls"
        aria-label="RAG 规则操作"
      >
        <div>
          <h3>RAG 规则生成</h3>
          <p>
            选择左侧真实漏洞，自动读取关联源码、检索参考材料并提炼检测规则。
          </p>
        </div>
        <div className="stage-row">
          <RuleGenerationForm
            key={current?.id ?? "none"}
            run={run}
            candidate={current}
            capabilities={capabilities}
            busy={busy}
          />
          {rule && (
            <RuleActions
              key={rule.id}
              rule={rule}
              awaiting={awaiting}
              busy={busy}
            />
          )}
        </div>
        <p className="page-note">
          使用自动生成策略；独立验收集与开发正反例分别验证，结果在右侧展示。
        </p>
        {latestStage?.status === "failed" && (
          <details>
            <summary>本次规则执行失败，查看原因</summary>
            <p role="alert">{latestStage.error}</p>
            <Link to="/knowledge" search={{ auditId: run.id }}>
              补充知识材料
            </Link>
          </details>
        )}
      </section>
      {candidates.error || rules.error ? (
        <p role="alert">
          读取失败：{candidates.error?.message ?? rules.error?.message}
        </p>
      ) : candidates.isPending || rules.isPending ? (
        <p role="status">正在读取漏洞与规则…</p>
      ) : (
        <section
          className="candidate-workspace result-workspace"
          aria-label="规则结果工作区"
        >
          <aside
            className="candidate-rail result-rail"
            aria-label="规则漏洞列表"
          >
            <div className="rail-heading">
              真实漏洞 <span>{confirmed.length} 项</span>
            </div>
            <div className="result-list">
              {confirmed.map((row) => {
                const versions = taskRules.filter(
                  (item) => sourceId(item.stage_id) === row.id,
                )
                return (
                  <button
                    type="button"
                    className="candidate-option"
                    key={row.id}
                    aria-pressed={current?.id === row.id}
                    onClick={() => {
                      setFocused(row.id)
                      setVersionId("")
                    }}
                  >
                    <span>{row.review?.detail?.title ?? row.title}</span>
                    <small>
                      {row.location.file}:{row.location.line} · {row.weakness}
                    </small>
                    <small>
                      {versions.length
                        ? `${versions.length} 个规则版本`
                        : "尚未生成规则"}
                    </small>
                  </button>
                )
              })}
              {standalone.map((row) => (
                <button
                  type="button"
                  className="candidate-option"
                  key={row.id}
                  aria-pressed={rule?.id === row.id}
                  onClick={() => {
                    setFocused(`rule:${row.id}`)
                    setVersionId("")
                  }}
                >
                  <span>{row.title}</span>
                  <small>独立规则 · {row.id.slice(0, 8)}</small>
                </button>
              ))}
              {!confirmed.length && !standalone.length && (
                <p className="page-note">
                  暂无确认真实的漏洞，请先完成 AI 复审。
                </p>
              )}
            </div>
          </aside>
          <section
            className="result-detail-scroll"
            aria-label="规则内容与验收结果"
            key={current?.id ?? standaloneRule?.id ?? "empty"}
          >
            <header className="result-detail-heading">
              <h3>
                {current?.review?.detail?.title ??
                  current?.title ??
                  standaloneRule?.title ??
                  "选择规则目标"}
              </h3>
              {current && (
                <p>
                  {current.location.file}:{current.location.line} ·{" "}
                  {current.weakness}
                </p>
              )}
              {related.length > 1 && (
                <label htmlFor={selectionId}>
                  规则版本{" "}
                  <WorkspaceSelect
                    id={selectionId}
                    className="native-select"
                    aria-label="查看规则版本"
                    value={rule?.id ?? ""}
                    onValueChange={setVersionId}
                    options={[
                      ...related.map((row, i) => ({
                        value: row.id,
                        label: (
                          <>
                            {i === 0 ? "最新版本" : "历史版本"} ·{" "}
                            {row.id.slice(0, 8)}
                          </>
                        ),
                      })),
                    ]}
                  />
                </label>
              )}
            </header>
            {rule ? (
              <RuleCard
                key={rule.id}
                rule={rule}
                awaiting={awaiting}
                embedded
              />
            ) : (
              <div className="downstream-empty">
                <h4>该漏洞尚未生成检测规则</h4>
                <p>
                  {current?.review?.reason ??
                    "在左侧选择目标后，点击上方生成检测规则。"}
                </p>
                <p>
                  生成后在这里查看查询代码、RAG 引用、正反例和项目验收结果。
                </p>
              </div>
            )}
          </section>
        </section>
      )}
      <details className="downstream-disclosure">
        <summary>后台执行历史</summary>
        <StageHistory stages={stages} />
      </details>
    </section>
  )
}
