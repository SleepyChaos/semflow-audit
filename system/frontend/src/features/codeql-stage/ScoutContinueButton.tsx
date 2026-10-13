import { useMutation, useQueryClient } from "@tanstack/react-query"
import { RotateCcw } from "lucide-react"
import { toast } from "sonner"
import type { AuditRun } from "@/api/audits"
import { continueScout, type StageRun } from "@/api/stages"
import { Button } from "@/components/ui/button"
import { activeStatus, scoutProgress } from "./discovery-state"

export function ScoutContinueButton({
  run,
  scout,
}: {
  run: AuditRun
  scout?: StageRun
}) {
  const cache = useQueryClient()
  const progress = scoutProgress(run, scout)
  const continuation = useMutation({
    mutationFn: () => continueScout(scout!.id),
    onSuccess: async (next) => {
      cache.setQueryData<StageRun[]>(["stages", run.id], (previous) => [
        next,
        ...(previous ?? []),
      ])
      await Promise.all([
        cache.invalidateQueries({ queryKey: ["stages", run.id] }),
        cache.invalidateQueries({ queryKey: ["candidates", run.id] }),
      ])
      if (next.status === "failed")
        toast.error(next.error ?? "补审任务启动失败")
      else toast.success("已启动未完成窗口补审，已有结果保留")
    },
  })
  const disabled =
    !scout ||
    progress.busy ||
    activeStatus(run.status) ||
    run.status === "cancelled" ||
    continuation.isPending ||
    progress.continuable === 0 ||
    !(
      progress.remaining ||
      ["partial", "failed", "cancelled"].includes(progress.status)
    )
  return (
    <div className="scout-continue-action">
      <Button disabled={disabled} onClick={() => continuation.mutate()}>
        <RotateCcw data-icon="inline-start" />
        {continuation.isPending
          ? "正在启动补审…"
          : progress.busy && scout?.inputs.continuation_from_id
            ? "未完成窗口补审中…"
            : "继续审计未完成窗口"}
      </Button>
      <p className="page-note">
        只检查当前范围内未完成的窗口，保留已检查记录和已有候选；每次补审仍受调用预算限制。
      </p>
      {continuation.error ? (
        <p role="alert">补审启动失败：{continuation.error.message}</p>
      ) : null}
    </div>
  )
}
