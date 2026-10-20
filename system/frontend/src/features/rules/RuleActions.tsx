import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import {
  approveFixtures,
  downloadQuery,
  publishRule,
  type RuleVersion,
  retireRule,
} from "@/api/stages"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { ProjectReplayReview } from "./ProjectReplayReview"

export function RuleActions({
  rule,
  awaiting,
  busy = false,
}: {
  rule: RuleVersion
  awaiting: boolean
  busy?: boolean
}) {
  const [reason, setReason] = useState("")
  const [open, setOpen] = useState(false)
  const cache = useQueryClient()
  const action = useMutation({
    mutationFn: (kind: string) =>
      kind === "approve"
        ? approveFixtures(rule.id, reason)
        : kind === "publish"
          ? publishRule(rule.id)
          : retireRule(rule.id),
    onSuccess: () => {
      setOpen(false)
      return cache.invalidateQueries()
    },
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <>
      <Button
        variant="outline"
        onClick={() =>
          downloadQuery(rule.id).catch((error: Error) =>
            toast.error(error.message),
          )
        }
      >
        下载当前查询
      </Button>
      {rule.status === "validated" && (
        <Button
          disabled={busy || action.isPending}
          onClick={() => action.mutate("publish")}
        >
          发布此版本
        </Button>
      )}
      {rule.status === "published" && (
        <Button
          variant="outline"
          disabled={busy || action.isPending}
          onClick={() => action.mutate("retire")}
        >
          停用此版本
        </Button>
      )}
      {awaiting && !rule.fixtures_approved && (
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button disabled={busy}>确认样本并继续验收</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>确认规则开发样本</DialogTitle>
              <DialogDescription>
                请先审阅规则详情中的正反例，确认样本能够表达漏洞条件和正常行为，再填写确认理由继续验收。
              </DialogDescription>
            </DialogHeader>
            <label>
              样本确认理由
              <textarea
                className="audit-textarea"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
            <Button
              disabled={busy || reason.trim().length < 10 || action.isPending}
              onClick={() => action.mutate("approve")}
            >
              批准样本并运行真实验收
            </Button>
          </DialogContent>
        </Dialog>
      )}
      {rule.validation.project_replay ? (
        <details className="result-action-review">
          <summary>项目复测与根因确认</summary>
          <ProjectReplayReview rule={rule} />
        </details>
      ) : null}
      {action.error && <p role="alert">{action.error.message}</p>}
    </>
  )
}
