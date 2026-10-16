import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowRight } from "lucide-react"
import { useEffect, useState } from "react"
import { toast } from "sonner"
import type { AuditRun } from "@/api/audits"
import {
  getCandidates,
  getRepairs,
  localizeRepairs,
  type StageRun,
  startStage,
} from "@/api/stages"
import { getVerificationSuites } from "@/api/verification"
import { Button } from "@/components/ui/button"
import { currentReviewCandidates } from "@/features/ai-review/review-status"
import { StageHistory } from "@/features/stages/StageHistory"
import { RepairActions } from "./RepairActions"
import { RepairCard } from "./RepairCard"
import { RepairProgressBadges, RepairTargets } from "./RepairTargets"
import { repairProgressState } from "./repair-progress"

export function RepairPanel({
  run,
  stages,
  modelReady,
}: {
  run: AuditRun
  stages: StageRun[]
  modelReady: boolean
}) {
  const [selected, setSelected] = useState<string[]>([])
  const [focused, setFocused] = useState("")
  const [recordId, setRecordId] = useState("")
  const cache = useQueryClient()
  const busy = stages.some((stage) =>
    ["queued", "running"].includes(stage.status),
  )
  const candidates = useQuery({
    queryKey: ["candidates", run.id],
    queryFn: () => getCandidates(run.id),
  })
  const repairs = useQuery({
    queryKey: ["repairs", run.id],
    queryFn: () => getRepairs(run.id),
    refetchInterval: (query) =>
      busy || query.state.data?.some((row) => row.localization_pending)
        ? 2500
        : false,
  })
  const translate = useMutation({
    mutationFn: () => localizeRepairs(run.id),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["repairs", run.id] }),
  })
  useEffect(() => {
    if (
      repairs.data?.some((row) => row.needs_localization) &&
      translate.isIdle &&
      modelReady
    )
      translate.mutate()
  }, [repairs.data, translate.isIdle, translate.mutate, modelReady])
  const suites = useQuery({
    queryKey: ["verification-suites", run.id],
    queryFn: () => getVerificationSuites(run.id),
    refetchInterval: busy ? 2500 : false,
  })
  const confirmed = currentReviewCandidates(candidates.data ?? []).filter(
    (row) =>
      row.classification?.status === "confirmed" ||
      (!row.classification && row.status === "confirmed"),
  )
  const targets = selected.filter((id) =>
    confirmed.some((row) => row.id === id),
  )
  const suite = targets.length
    ? suites.data?.find((row) =>
        targets.every((id) => row.candidate_ids.includes(id)),
      )
    : undefined
  const current = confirmed.find((row) => row.id === focused) ?? confirmed[0]
  const records = [...(repairs.data ?? [])].sort((a, b) => {
    const time = (id: string) =>
      stages.find((stage) => stage.id === id)?.created_at ?? ""
    return time(b.stage_id).localeCompare(time(a.stage_id))
  })
  const related = records.filter((row) =>
    row.candidate_ids.includes(current?.id ?? ""),
  )
  const record = related.find((row) => row.id === recordId) ?? related[0]
  const start = useMutation({
    mutationFn: () =>
      startStage(run.id, "repair", {
        candidate_ids: targets,
        allowed_paths: [],
        validation_profile: "syntax",
        rescan: true,
        ...(suite ? { verification_suite_id: suite.id } : {}),
      }),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <section className="stage-section downstream-workspace">
      <section
        className="action-banner result-controls"
        aria-label="代码修复操作"
      >
        <div>
          <h3>代码修复</h3>
          <p>
            勾选真实漏洞生成补丁，点击左侧条目查看对应的修复记录、验证结果和代码
            Diff。
          </p>
        </div>
        <div className="stage-row">
          <Button
            disabled={!modelReady || !targets.length || busy || start.isPending}
            onClick={() => start.mutate()}
          >
            {start.isPending
              ? "正在提交…"
              : `生成修复补丁${targets.length ? `（${targets.length} 项）` : ""}`}
          </Button>
          <ArrowRight
            className="repair-flow-arrow"
            size={18}
            aria-hidden="true"
          />
          <RepairActions
            key={record?.id ?? "empty"}
            auditId={run.id}
            record={record}
            busy={busy}
            modelReady={modelReady}
          />
        </div>
        {translate.error && (
          <p role="alert">中文修复解读生成失败：{translate.error.message}</p>
        )}
        <p className="page-note">
          自动读取关联文件，使用平台验证环境、语法检查及 CodeQL 复扫；
          {suite
            ? "已匹配固定测试集，新补丁会按该测试集的预期行为修复并执行验证。"
            : "前后验证使用匹配的固定测试集。"}
        </p>
        {start.error && <p role="alert">{start.error.message}</p>}
      </section>
      {candidates.error || repairs.error ? (
        <p role="alert">
          读取失败：{candidates.error?.message ?? repairs.error?.message}
        </p>
      ) : candidates.isPending || repairs.isPending ? (
        <p role="status">正在读取漏洞和修复记录…</p>
      ) : (
        <section
          className="candidate-workspace result-workspace"
          aria-label="修复结果工作区"
        >
          <RepairTargets
            candidates={confirmed}
            selected={targets}
            focused={current?.id}
            onSelect={setSelected}
            onFocus={(id) => {
              setFocused(id)
              setRecordId("")
            }}
            busy={busy}
            records={records}
            stages={stages}
          />
          <section
            className="result-detail-scroll"
            aria-label="修复验证与代码对比"
            key={current?.id ?? "empty"}
          >
            {current ? (
              <>
                <header className="result-detail-heading">
                  <h3>{current.review?.detail?.title ?? current.title}</h3>
                  <p>
                    {current.location.file}:{current.location.line} ·{" "}
                    {current.weakness}
                  </p>
                  <RepairProgressBadges
                    progress={repairProgressState(stages, records, current.id)}
                  />
                  {related.length > 1 && (
                    <label>
                      修复记录{" "}
                      <select
                        className="native-select"
                        aria-label="查看修复记录"
                        value={record?.id ?? ""}
                        onChange={(e) => setRecordId(e.target.value)}
                      >
                        {related.map((row, i) => (
                          <option value={row.id} key={row.id}>
                            {i === 0 ? "最新尝试" : "历史尝试"} ·{" "}
                            {row.id.slice(0, 8)}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                </header>
                {record ? (
                  <>
                    <p className="page-note">
                      本补丁关联 {record.candidate_ids.length}{" "}
                      个修复目标，下方展示完整补丁及实际验证范围。
                    </p>
                    <RepairCard
                      key={record.id}
                      record={record}
                      auditId={run.id}
                    />
                  </>
                ) : (
                  <div className="downstream-empty">
                    <h4>该漏洞尚未生成补丁</h4>
                    <p>勾选左侧目标后，使用上方“生成修复补丁”开始修复。</p>
                  </div>
                )}
              </>
            ) : (
              <div className="downstream-empty">
                <h4>暂无可修复的真实漏洞</h4>
                <p>先在 AI 复审中确认漏洞分类。</p>
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
