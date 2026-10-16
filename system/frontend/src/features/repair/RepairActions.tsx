import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowRight } from "lucide-react"
import { toast } from "sonner"
import { acceptRepair, downloadDiff, type RepairRecord } from "@/api/stages"
import {
  generateVerificationSuite,
  getVerificationSuites,
  verifyRepair,
} from "@/api/verification"
import { Button } from "@/components/ui/button"

export function RepairActions({
  auditId,
  record,
  busy,
  modelReady,
}: {
  auditId: string
  record?: RepairRecord
  busy: boolean
  modelReady: boolean
}) {
  const cache = useQueryClient()
  const suites = useQuery({
    queryKey: ["verification-suites", auditId],
    queryFn: () => getVerificationSuites(auditId),
    refetchInterval: busy ? 2500 : false,
  })
  const suite =
    record &&
    suites.data?.find((row) =>
      record.candidate_ids.every((id) => row.candidate_ids.includes(id)),
    )
  const suiteId = suite?.id || record?.comparison?.identity?.suite_id
  const applicationFailed =
    (record?.validation.application as { status?: string } | undefined)
      ?.status === "failed"
  const action = useMutation({
    mutationFn: (kind: "suite" | "verify" | "accept") => {
      if (kind === "suite")
        return generateVerificationSuite(auditId, {
          candidate_ids: record!.candidate_ids,
          image: suite?.image ?? "",
          requirements: "",
        })
      if (kind === "verify") return verifyRepair(record!.id, suiteId!)
      return acceptRepair(
        record!.id,
        "用户已审阅补丁、测试断言及前后对比，接受所列测试范围内的修复。",
        record!.comparison?.stage_id,
        true,
      )
    },
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  const disabled =
    !record || busy || action.isPending || record.status === "accepted"
  return (
    <>
      <Button
        variant="outline"
        disabled={disabled || !modelReady}
        onClick={() => action.mutate("suite")}
      >
        生成验收测试
      </Button>
      <ArrowRight className="repair-flow-arrow" size={18} aria-hidden="true" />
      <Button
        variant="outline"
        disabled={disabled || !suiteId || applicationFailed}
        onClick={() => action.mutate("verify")}
      >
        修复前后对比
      </Button>
      <ArrowRight className="repair-flow-arrow" size={18} aria-hidden="true" />
      <Button
        variant="outline"
        disabled={!record}
        onClick={() =>
          downloadDiff(record!.id).catch((error: Error) =>
            toast.error(error.message),
          )
        }
      >
        下载当前 Diff
      </Button>
      {record?.acceptance_ready && record.status !== "accepted" && (
        <Button disabled={disabled} onClick={() => action.mutate("accept")}>
          审阅后接受补丁
        </Button>
      )}
      {suites.error && (
        <p role="alert">测试集读取失败：{suites.error.message}</p>
      )}
      {action.error && <p role="alert">{action.error.message}</p>}
      {record && (
        <p className="result-action-note">
          当前补丁 {record.id.slice(0, 8)} ·{" "}
          {suiteId
            ? "已匹配固定测试集"
            : "尚无匹配测试集，先生成验收测试再运行前后对比"}
        </p>
      )}
    </>
  )
}
