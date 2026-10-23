import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowRight } from "lucide-react"
import { toast } from "sonner"
import { downloadDiff, type RepairRecord } from "@/api/stages"
import {
  generateVerificationSuite,
  getVerificationSuites,
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
  const action = useMutation({
    mutationFn: () =>
      generateVerificationSuite(auditId, {
        candidate_ids: record!.candidate_ids,
        image: suite?.image ?? "",
        requirements: "",
      }),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <>
      <Button
        variant="outline"
        disabled={!record || busy || action.isPending || !modelReady}
        onClick={() => action.mutate()}
      >
        生成测试样例
      </Button>
      <ArrowRight className="repair-flow-arrow" size={18} aria-hidden="true" />
      <Button
        variant="outline"
        disabled={!record?.changes.length}
        onClick={() =>
          downloadDiff(record!.id).catch((error: Error) =>
            toast.error(error.message),
          )
        }
      >
        下载修复 Diff
      </Button>
      {suites.error && (
        <p role="alert">测试样例读取失败：{suites.error.message}</p>
      )}
      {action.error && <p role="alert">{action.error.message}</p>}
      {record && (
        <p className="result-action-note">
          当前补丁 {record.id.slice(0, 8)} ·{" "}
          {suite
            ? "测试样例已生成，可下载修复 Diff"
            : "补丁已生成，可生成关联测试样例"}
        </p>
      )}
    </>
  )
}
