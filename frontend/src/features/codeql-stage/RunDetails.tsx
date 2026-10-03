import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Download, RotateCcw } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"
import {
  type AuditRun,
  cancelRun,
  downloadSarif,
  getLogs,
  recoverRun,
  retryRun,
} from "@/api/audits"
import { getCapabilities, getStages } from "@/api/stages"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ReviewPanel } from "@/features/ai-review/ReviewPanel"
import { RepairPanel } from "@/features/repair/RepairPanel"
import { RulePanel } from "@/features/rules/RulePanel"
import { FindingDetails } from "./FindingDetails"

const phases: Record<string, string> = {
  queued: "等待后台执行",
  database: "正在建立 CodeQL 数据库",
  scan: "正在运行漏洞查询",
  parse: "正在保存告警证据",
  supplement: "正在执行补充规则",
  cancelled: "扫描已取消",
  completed: "静态扫描完成",
}
export function RunDetails({
  run,
  onCreated,
  activeStage,
  onStageChange,
}: {
  run: AuditRun
  activeStage: string
  onStageChange: (stage: string) => void
  onCreated: (id: string) => void
}) {
  const [findingId, setFindingId] = useState<string | null>(null)
  const cache = useQueryClient()
  const stages = useQuery({
    queryKey: ["stages", run.id],
    queryFn: () => getStages(run.id),
    refetchInterval: (query) =>
      query.state.data?.some((item) =>
        ["queued", "running"].includes(item.status),
      )
        ? 2500
        : false,
  })
  const capabilities = useQuery({
    queryKey: ["capabilities"],
    queryFn: getCapabilities,
    refetchInterval: 15000,
  })
  const logs = useQuery({
    queryKey: ["logs", run.id],
    queryFn: () => getLogs(run.id),
    refetchInterval: run.status === "running" ? 3000 : false,
  })
  const retry = useMutation({
    mutationFn: () => retryRun(run.id),
    onSuccess: async (next) => {
      await cache.invalidateQueries({ queryKey: ["audits"] })
      onCreated(next.id)
    },
    onError: (error: Error) => toast.error(error.message),
  })
  const control = useMutation({
    mutationFn: (action: "cancel" | "recover") =>
      action === "cancel" ? cancelRun(run.id) : recoverRun(run.id),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["audits"] }),
    onError: (error: Error) => toast.error(error.message),
  })
  const finding = run.findings.find((item) => item.id === findingId)
  return (
    <section className="detail-panel">
      <header className="detail-heading">
        <div>
          <h2>{run.project_name}</h2>
          <p>{phases[run.phase] ?? run.phase}</p>
        </div>
        {run.status === "completed" ? (
          <Button
            variant="outline"
            onClick={() =>
              downloadSarif(run.id).catch((error: Error) =>
                toast.error(error.message),
              )
            }
          >
            <Download data-icon="inline-start" />
            下载 SARIF
          </Button>
        ) : null}
        {["queued", "running"].includes(run.status) ? (
          <Button
            variant="outline"
            disabled={control.isPending}
            onClick={() => control.mutate("cancel")}
          >
            取消扫描
          </Button>
        ) : null}
        {run.status === "running" ? (
          <Button
            variant="outline"
            disabled={control.isPending}
            onClick={() => control.mutate("recover")}
          >
            回收无进展执行
          </Button>
        ) : null}
        {["failed", "cancelled"].includes(run.status) ? (
          <Button
            variant="outline"
            disabled={retry.isPending}
            onClick={() => retry.mutate()}
          >
            <RotateCcw data-icon="inline-start" />
            创建重试任务
          </Button>
        ) : null}
      </header>
      <Tabs value={activeStage} onValueChange={onStageChange}>
        <TabsList>
          <TabsTrigger value="codeql">CodeQL 审计</TabsTrigger>
          <TabsTrigger value="ai">AI 复审</TabsTrigger>
          <TabsTrigger value="repair">修复与报告</TabsTrigger>
          <TabsTrigger value="rag">RAG 规则</TabsTrigger>
        </TabsList>
        <TabsContent value="codeql">
          {run.error ? (
            <Alert variant="destructive">
              <AlertTitle>审计未完成</AlertTitle>
              <AlertDescription>{run.error}</AlertDescription>
            </Alert>
          ) : null}
          <dl className="run-metadata">
            <div>
              <dt>代码快照</dt>
              <dd>{run.snapshot_hash.slice(0, 16)}</dd>
            </div>
            <div>
              <dt>CodeQL</dt>
              <dd>{run.codeql_version ?? "待执行"}</dd>
            </div>
            <div>
              <dt>查询包</dt>
              <dd>{run.query_pack}</dd>
            </div>
          </dl>
          {run.coverage.unscanned_languages?.length ? (
            <Alert>
              <AlertTitle>覆盖范围</AlertTitle>
              <AlertDescription>
                本次未扫描：{run.coverage.unscanned_languages.join("、")}
              </AlertDescription>
            </Alert>
          ) : null}
          {run.status === "completed" && !run.findings.length ? (
            <p className="py-5">本次规则集未报告告警，不代表代码不存在漏洞。</p>
          ) : null}
          <div className="findings-list">
            {run.findings.map((item) => (
              <Button
                key={item.id}
                variant={findingId === item.id ? "secondary" : "ghost"}
                className="finding-button"
                onClick={() => setFindingId(item.id)}
              >
                {item.rule} · {item.locations[0].file}:{item.locations[0].line}
              </Button>
            ))}
          </div>
          {finding ? (
            <FindingDetails key={finding.id} finding={finding} runId={run.id} />
          ) : null}
          <details className="execution-log">
            <summary>执行日志</summary>
            <pre>
              {logs.error
                ? logs.error.message
                : logs.data?.text || "暂无执行日志"}
            </pre>
          </details>
        </TabsContent>
        <TabsContent value="ai">
          <ReviewPanel
            run={run}
            stages={(stages.data ?? []).filter(
              (item) => item.kind === "review",
            )}
            modelReady={Boolean(capabilities.data?.model_configured)}
          />
        </TabsContent>
        <TabsContent value="repair">
          <RepairPanel
            run={run}
            stages={(stages.data ?? []).filter(
              (item) => item.kind === "repair",
            )}
            modelReady={Boolean(capabilities.data?.model_configured)}
          />
        </TabsContent>
        <TabsContent value="rag">
          <RulePanel
            run={run}
            stages={(stages.data ?? []).filter((item) => item.kind === "rule")}
            capabilities={capabilities.data}
          />
        </TabsContent>
        {stages.error ? <p role="alert">{stages.error.message}</p> : null}
      </Tabs>
    </section>
  )
}
