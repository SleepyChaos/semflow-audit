import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Download, RotateCcw } from "lucide-react"
import { toast } from "sonner"
import {
  type AuditRun,
  cancelRun,
  downloadSarif,
  recoverRun,
  retryRun,
} from "@/api/audits"
import { getCapabilities, getStages } from "@/api/stages"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent } from "@/components/ui/tabs"
import { ReviewPanel } from "@/features/ai-review/ReviewPanel"
import { RepairPanel } from "@/features/repair/RepairPanel"
import { RulePanel } from "@/features/rules/RulePanel"
import { DiscoveryPanel } from "./DiscoveryPanel"
import { reviewBlockReason } from "./discovery-state"

const phases: Record<string, string> = {
  queued: "等待后台执行",
  database: "正在建立 CodeQL 数据库",
  scan: "正在运行漏洞查询",
  parse: "正在保存告警证据",
  supplement: "正在执行补充规则",
  cancelled: "扫描已取消",
  completed: "静态扫描完成",
  codeql_ready: "CodeQL 完成，等待 Agent 汇合",
  discovery_ready: "双引擎发现完成，等待复核",
  discovery_partial: "双引擎部分完成，请查看各路覆盖",
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
  const cache = useQueryClient()
  const stages = useQuery({
    queryKey: ["stages", run.id],
    queryFn: () => getStages(run.id),
    refetchInterval: (query) =>
      ["queued", "running"].includes(run.status) ||
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
    onSuccess: () =>
      Promise.all([
        cache.invalidateQueries({ queryKey: ["audits"] }),
        cache.invalidateQueries({ queryKey: ["audit", run.id] }),
      ]),
    onError: (error: Error) => toast.error(error.message),
  })
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
        <TabsContent value="codeql">
          <DiscoveryPanel
            key={run.id}
            run={run}
            stages={stages.data ?? []}
            stagesPending={stages.isPending}
            stagesError={stages.error}
            onReloadStages={() => {
              void stages.refetch()
            }}
            onReview={() => onStageChange("ai")}
            reviewBlockedReason={reviewBlockReason(run, stages.data ?? [], {
              pending: stages.isPending,
              error: stages.error,
            })}
          />
        </TabsContent>
        <TabsContent value="ai">
          <ReviewPanel
            run={run}
            stages={(stages.data ?? []).filter(
              (item) => item.kind === "review" || item.kind === "scout",
            )}
            modelReady={Boolean(capabilities.data?.model_configured)}
          />
        </TabsContent>
        <TabsContent value="repair">
          <RepairPanel
            run={run}
            stages={(stages.data ?? []).filter((item) =>
              [
                "repair",
                "report",
                "verification",
                "verification_suite",
                "verification_acceptance",
              ].includes(item.kind),
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
