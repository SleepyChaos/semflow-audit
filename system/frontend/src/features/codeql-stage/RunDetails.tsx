import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { RotateCcw } from "lucide-react"
import { toast } from "sonner"
import { type AuditRun, cancelRun, recoverRun, retryRun } from "@/api/audits"
import { getCapabilities, getStages } from "@/api/stages"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent } from "@/components/ui/tabs"
import { ReviewPanel } from "@/features/ai-review/ReviewPanel"
import { RepairPanel } from "@/features/repair/RepairPanel"
import { ReportPanel } from "@/features/repair/ReportPanel"
import { RulePanel } from "@/features/rules/RulePanel"
import { AuditExecutionLogs } from "@/features/shell/AuditExecutionLogs"
import { DiscoveryPanel } from "./DiscoveryPanel"

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
      {activeStage === "codeql" && run.status !== "completed" ? (
        <div className="stage-row scan-execution-actions">
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
        </div>
      ) : null}
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
          <AuditExecutionLogs key={run.id} auditId={run.id} />
        </TabsContent>
        <TabsContent value="report">
          <ReportPanel
            run={run}
            stages={(stages.data ?? []).filter(
              (item) => item.kind === "report",
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
