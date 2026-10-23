import type { RepairRecord, StageRun } from "@/api/stages"
import type { WorkflowStep } from "@/features/stages/WorkflowSteps"

const running = (status?: string) =>
  ["queued", "running"].includes(status ?? "")
const newest = (rows: StageRun[]) =>
  [...rows].sort((a, b) => b.created_at.localeCompare(a.created_at))[0]

export function repairProgressState(
  stages: StageRun[],
  records: RepairRecord[],
  candidate?: string | string[],
) {
  const candidateIds = typeof candidate === "string" ? [candidate] : candidate
  const latestRepair = newest(
    stages.filter(
      (stage) =>
        stage.kind === "repair" &&
        (!candidateIds ||
          candidateIds.some((id) =>
            (
              (stage.inputs.candidate_ids ?? stage.result.candidate_ids) as
                | string[]
                | undefined
            )?.includes(id),
          )),
    ),
  )
  const related = records.filter(
    (row) =>
      !candidateIds ||
      candidateIds.some((id) => row.candidate_ids.includes(id)),
  )
  const latestRecord = related.find((row) => row.stage_id === latestRepair?.id)
  const record =
    (latestRecord && hasRepairPatch(latestRecord) ? latestRecord : undefined) ??
    [...related]
      .sort((a, b) =>
        (
          stages.find((x) => x.id === b.stage_id)?.created_at ?? ""
        ).localeCompare(
          stages.find((x) => x.id === a.stage_id)?.created_at ?? "",
        ),
      )
      .find(hasRepairPatch) ??
    latestRecord
  const repair = running(latestRepair?.status)
    ? latestRepair
    : (stages.find((row) => row.id === record?.stage_id) ?? latestRepair)
  const hasPatch = Boolean(record && hasRepairPatch(record))
  const targets = record?.candidate_ids ?? candidateIds ?? []
  const suite = newest(
    stages.filter(
      (stage) =>
        stage.kind === "verification_suite" &&
        targets.length > 0 &&
        targets.every((id) =>
          (
            (stage.inputs.candidate_ids ?? stage.result.candidate_ids) as
              | string[]
              | undefined
          )?.includes(id),
        ),
    ),
  )
  const suiteReady =
    suite?.status === "completed" ||
    Boolean(record?.comparison?.identity?.suite_id)
  const steps: WorkflowStep[] = [
    {
      title: "生成修复补丁",
      detail: running(repair?.status)
        ? "正在生成修复补丁"
        : hasPatch
          ? "补丁已生成，可查看代码 Diff"
          : repair?.status === "failed"
            ? "补丁生成失败，可重新生成"
            : "勾选漏洞后生成补丁",
      status: running(repair?.status)
        ? "active"
        : hasPatch
          ? "done"
          : repair?.status === "failed"
            ? "attention"
            : "waiting",
    },
    {
      title: "生成测试样例",
      detail: running(suite?.status)
        ? "正在生成测试样例"
        : suiteReady
          ? "关联测试样例已准备"
          : "生成覆盖修复目标的测试样例",
      status: running(suite?.status)
        ? "active"
        : suiteReady
          ? "done"
          : suite?.status === "failed"
            ? "attention"
            : hasPatch
              ? "active"
              : "waiting",
    },
    {
      title: "下载修复 Diff",
      detail: hasPatch
        ? "可下载补丁文件，在原项目中查看和应用修改"
        : "生成补丁后可下载修复 Diff",
      status: hasPatch && suiteReady ? "done" : "waiting",
      statusLabel: hasPatch && suiteReady ? "可下载" : "待准备",
    },
  ]
  const current = steps.find((step) => step.status !== "done") ?? steps[2]
  return { steps, hasPatch, record, current }
}

export function hasRepairPatch(record: RepairRecord) {
  const application = record.validation.application as
    | { status?: string }
    | undefined
  const scope = record.validation.semantic_scope as
    | { workspace_snapshot?: string }
    | undefined
  const tests = record.validation.isolated_tests as
    | { patched_snapshot_hash?: string }
    | undefined
  const rescan = record.validation.rescan as
    | { patched_snapshot_hash?: string }
    | undefined
  return Boolean(
    record.changes.length &&
      application?.status !== "failed" &&
      (scope?.workspace_snapshot ||
        tests?.patched_snapshot_hash ||
        rescan?.patched_snapshot_hash ||
        application?.status === "passed"),
  )
}
