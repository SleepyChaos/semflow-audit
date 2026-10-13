import { useQuery } from "@tanstack/react-query"
import { ChevronRight } from "lucide-react"
import { useState } from "react"
import type { AuditRun } from "@/api/audits"
import { getCandidates, type StageRun } from "@/api/stages"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { humanStatuses } from "@/features/ai-review/CandidateWorkspace"
import { uniqueCandidates } from "@/features/audit-task/task-summary"
import { labelPhase, labelStatus } from "@/features/stages/stage-labels"
import { CodeqlResults } from "./CodeqlResults"
import { DiscoveryCandidate } from "./DiscoveryCandidate"
import {
  activeStatus,
  currentScout,
  scoutProgress,
  scoutSourceIds,
} from "./discovery-state"
import { ScoutContinueButton } from "./ScoutContinueButton"

export function DiscoveryPanel({
  run,
  stages,
  stagesPending,
  stagesError,
  onReloadStages,
  onReview,
  reviewBlockedReason,
}: {
  run: AuditRun
  stages: StageRun[]
  stagesPending: boolean
  stagesError: Error | null
  onReloadStages: () => void
  onReview: () => void
  reviewBlockedReason: string | null
}) {
  const [candidateId, setCandidateId] = useState<string | null>(null)
  const scout = currentScout(run, stages)
  const progress = scoutProgress(run, scout)
  const scoutIds = scoutSourceIds(run, scout)
  const candidates = useQuery({
    queryKey: ["candidates", run.id],
    queryFn: () => getCandidates(run.id),
    retry: false,
    refetchInterval: activeStatus(run.status) || progress.busy ? 3000 : false,
  })
  const aiCandidates = uniqueCandidates(
    (candidates.data ?? []).filter(
      (item) =>
        item.audit_id === run.id &&
        item.origin === "ai" &&
        scoutIds.has(item.stage_id),
    ),
  )
  const candidate = aiCandidates.find((item) => item.id === candidateId)
  const emptyMessage = progress.busy
    ? "AI 初审正在执行，尚未保存候选；新发现会自动更新。"
    : ["failed", "cancelled"].includes(progress.status)
      ? "AI 初审未完成，当前没有已保存候选，不能据此判断项目安全。"
      : progress.status === "not_run"
        ? "该任务未运行 AI 初审，可在 AI 复审页单独启动。"
        : progress.status === "unknown"
          ? "尚未获得 AI 初审结果，不能据此判断项目安全。"
          : "已检查范围暂无已保存候选，不代表整个项目安全。"
  return (
    <div className="discovery-grid">
      <CodeqlResults key={run.id} run={run} />
      <Card className="discovery-engine" aria-label="AI 初审">
        <CardHeader>
          <div className="discovery-heading">
            <CardTitle>
              <h3>AI 初审</h3>
            </CardTitle>
            <Badge
              variant={
                progress.status === "failed" ? "destructive" : "secondary"
              }
            >
              {stagesError
                ? "状态无法读取"
                : stagesPending
                  ? "正在读取"
                  : progress.status === "completed"
                    ? "检查结束"
                    : labelStatus(progress.status)}
            </Badge>
          </div>
          <CardDescription>
            独立分析同一源码快照 · 初审候选与静态告警分别展示
          </CardDescription>
        </CardHeader>
        <CardContent
          className="discovery-content discovery-scroll"
          role="region"
          aria-label="AI 初审结果滚动区域"
          tabIndex={0}
        >
          {stagesError ? (
            <Alert variant="destructive">
              <AlertTitle>AI 执行状态读取失败</AlertTitle>
              <AlertDescription>
                <p>{stagesError.message}</p>
                <Button variant="outline" size="sm" onClick={onReloadStages}>
                  重新读取状态
                </Button>
              </AlertDescription>
            </Alert>
          ) : stagesPending ? (
            <p role="status">正在读取 AI 初审状态…</p>
          ) : (
            <>
              <dl className="discovery-stats" aria-live="polite">
                <div>
                  <dt>已检查窗口</dt>
                  <dd>
                    {scout || progress.total !== undefined
                      ? progress.completed
                      : "—"}
                    {progress.total !== undefined ? ` / ${progress.total}` : ""}
                  </dd>
                </div>
                <div>
                  <dt>初审候选</dt>
                  <dd>
                    {candidates.error
                      ? "无法读取"
                      : candidates.isPending
                        ? "读取中"
                        : aiCandidates.length}
                  </dd>
                </div>
                <div>
                  <dt>模型调用</dt>
                  <dd>{progress.calls ?? "—"}</dd>
                </div>
              </dl>
              <p className="page-note" role="status">
                {progress.busy
                  ? scout
                    ? labelPhase(scout.phase)
                    : "等待 AI 初审启动"
                  : labelStatus(progress.status)}
                {scout?.updated_at
                  ? ` · 更新于 ${new Date(scout.updated_at).toLocaleTimeString()}`
                  : ""}
              </p>
              {progress.error ||
              progress.stop ||
              progress.status === "partial" ? (
                <Alert variant={progress.error ? "destructive" : "default"}>
                  <AlertTitle>
                    {progress.error ? "AI 初审未完成" : "AI 覆盖范围未完成"}
                  </AlertTitle>
                  <AlertDescription>
                    {progress.error ??
                      progress.stop ??
                      "本次执行结束，仍有范围未检查。"}
                    {progress.remaining !== undefined
                      ? ` · ${progress.remaining} 个窗口未检查。`
                      : ""}
                    已保存的候选保留，可以继续查看和复核。
                  </AlertDescription>
                </Alert>
              ) : null}
              <ScoutContinueButton
                key={scout?.id ?? run.id}
                run={run}
                scout={scout}
              />
              {progress.files.length || progress.incomplete.length ? (
                <details className="discovery-coverage">
                  <summary>查看文件覆盖与未完成原因</summary>
                  {progress.files.map((file) => (
                    <p key={file.name}>
                      {file.name} · 已检查 {file.completed ?? "—"} /{" "}
                      {file.total ?? "—"} 个窗口
                    </p>
                  ))}
                  {progress.incomplete.map((unit, index) => (
                    <p key={String(unit.unit_id ?? index)}>
                      未完成：{String(unit.reason ?? "原因尚未记录")}
                    </p>
                  ))}
                </details>
              ) : null}
              <p className="page-note">
                窗口检查计数表示分析范围，不代表安全结论或全项目审计百分比。
              </p>
            </>
          )}
          {candidates.error ? (
            <Alert variant="destructive">
              <AlertTitle>AI 候选读取失败</AlertTitle>
              <AlertDescription>
                <p>{candidates.error.message}</p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => candidates.refetch()}
                >
                  重新读取候选
                </Button>
              </AlertDescription>
            </Alert>
          ) : candidates.isPending ? (
            <p role="status">正在读取 AI 候选…</p>
          ) : (
            <>
              {!aiCandidates.length && !stagesPending && !stagesError ? (
                <p role="status" className="page-note">
                  {emptyMessage}
                </p>
              ) : null}
              <div className="findings-list discovery-candidates">
                {aiCandidates.map((item) => (
                  <Button
                    type="button"
                    key={item.id}
                    variant={candidateId === item.id ? "default" : "secondary"}
                    className="finding-button"
                    aria-pressed={candidateId === item.id}
                    aria-controls={`ai-candidate-detail-${run.id}`}
                    onClick={() => setCandidateId(item.id)}
                  >
                    <span className="finding-label">
                      <strong>{item.title}</strong>
                      <span>
                        {item.location.file ?? "位置待核实"}:
                        {item.location.line ?? "—"} ·{" "}
                        {humanStatuses[item.status] ?? item.status}
                      </span>
                    </span>
                    <ChevronRight data-icon="inline-end" />
                  </Button>
                ))}
              </div>
              <div id={`ai-candidate-detail-${run.id}`}>
                {candidate ? (
                  <DiscoveryCandidate
                    key={candidate.id}
                    candidate={candidate}
                    run={run}
                  />
                ) : null}
              </div>
            </>
          )}
        </CardContent>
        <CardFooter className="discovery-review-action">
          <Button
            variant="outline"
            disabled={Boolean(reviewBlockedReason)}
            aria-describedby={
              reviewBlockedReason ? "discovery-review-block-reason" : undefined
            }
            onClick={onReview}
          >
            进入 AI 复审
            <ChevronRight data-icon="inline-end" />
          </Button>
          {reviewBlockedReason ? (
            <p
              id="discovery-review-block-reason"
              role="status"
              className="page-note"
            >
              {reviewBlockedReason}
            </p>
          ) : null}
        </CardFooter>
      </Card>
    </div>
  )
}
