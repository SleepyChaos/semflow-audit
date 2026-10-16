import type { RepairRecord, StageRun } from "@/api/stages"
import type { WorkflowStep } from "@/features/stages/WorkflowSteps"

const running = (status?: string) =>
  ["queued", "running"].includes(status ?? "")
const newest = (rows: StageRun[]) =>
  [...rows].sort((a, b) => b.created_at.localeCompare(a.created_at))[0]

export function repairProgressState(
  stages: StageRun[],
  records: RepairRecord[],
  candidateId?: string,
) {
  const repair = newest(
    stages.filter(
      (stage) =>
        stage.kind === "repair" &&
        (!candidateId ||
          (stage.inputs.candidate_ids as string[] | undefined)?.includes(
            candidateId,
          )),
    ),
  )
  const record = records.find((row) => row.stage_id === repair?.id)
  const application = record?.validation.application as
    | { status?: string }
    | undefined
  const scope = record?.validation.semantic_scope as
    | { workspace_snapshot?: string }
    | undefined
  const tests = record?.validation.isolated_tests as
    | { status?: string; patched_snapshot_hash?: string }
    | undefined
  const rescan = record?.validation.rescan as
    | { status?: string; patched_snapshot_hash?: string }
    | undefined
  const hasPatch = Boolean(
    record?.changes.length &&
      application?.status !== "failed" &&
      (scope?.workspace_snapshot ||
        tests?.patched_snapshot_hash ||
        rescan?.patched_snapshot_hash ||
        application?.status === "passed"),
  )
  const targets = candidateId ? [candidateId] : (record?.candidate_ids ?? [])
  const suite = newest(
    stages.filter(
      (stage) =>
        stage.kind === "verification_suite" &&
        targets.length > 0 &&
        targets.every((id) =>
          (stage.inputs.candidate_ids as string[] | undefined)?.includes(id),
        ),
    ),
  )
  const verification = newest(
    stages.filter(
      (stage) =>
        stage.kind === "verification" && stage.inputs.repair_id === record?.id,
    ),
  )
  const comparison = record?.comparison
  const suiteReady =
    suite?.status === "completed" || Boolean(comparison?.identity?.suite_id)
  const steps: WorkflowStep[] = [
    {
      title: "生成修复补丁",
      detail: running(repair?.status)
        ? "正在生成修复补丁"
        : repair?.status === "failed"
          ? "本次补丁生成失败，可重试"
          : application?.status === "failed"
            ? "补丁未能应用到源码"
            : hasPatch
              ? "补丁已生成，尚需验证修复效果"
              : "勾选漏洞后生成补丁",
      status: running(repair?.status)
        ? "active"
        : repair?.status === "failed" || application?.status === "failed"
          ? "attention"
          : hasPatch
            ? "done"
            : "waiting",
    },
    {
      title: "生成验收测试",
      detail: running(suite?.status)
        ? "正在生成验收测试"
        : suite?.status === "failed"
          ? "测试生成失败，可重试"
          : suiteReady
            ? "关联目标的测试集已准备"
            : "生成覆盖修复目标的测试集",
      status: running(suite?.status)
        ? "active"
        : suite?.status === "failed"
          ? "attention"
          : suiteReady
            ? "done"
            : hasPatch
              ? "active"
              : "waiting",
    },
    verificationStep(
      record,
      verification,
      candidateId,
      tests?.status,
      rescan?.status,
      hasPatch && suiteReady,
    ),
    {
      title: "交付补丁",
      detail:
        record?.status === "accepted"
          ? "补丁已接受，可下载"
          : record?.acceptance_ready
            ? "验证已通过，等待接受补丁"
            : "验证通过后审阅并接受补丁",
      status:
        record?.status === "accepted"
          ? "done"
          : record?.acceptance_ready
            ? "active"
            : "waiting",
    },
  ]
  // A later step cannot be current while an earlier step is still blocked.
  const currentIndex = steps.findIndex((step) => step.status !== "done")
  for (let i = currentIndex + 1; currentIndex >= 0 && i < steps.length; i++) {
    if (steps[i].status === "active") steps[i].status = "waiting"
  }
  return { steps, hasPatch, record, current: steps[currentIndex] ?? steps[3] }
}

function verificationStep(
  record: RepairRecord | undefined,
  stage: StageRun | undefined,
  candidateId: string | undefined,
  syntax: string | undefined,
  rescan: string | undefined,
  ready: boolean,
): WorkflowStep {
  const step: WorkflowStep = {
    title: "修复前后对比",
    detail: "等待运行修复前后对比",
    status: ready ? "active" : "waiting",
  }
  const comparison = record?.comparison
  if (running(stage?.status) || running(comparison?.status))
    return { ...step, detail: "正在对比修复前后的测试结果", status: "active" }
  if (stage?.status === "failed")
    return { ...step, detail: "验证执行失败，可重新运行", status: "attention" }
  if (stage?.status === "cancelled" || comparison?.status === "cancelled")
    return { ...step, detail: "验证已取消，尚未完成", status: "attention" }
  const cases =
    comparison?.cases?.filter(
      (test) => !candidateId || test.candidate_ids.includes(candidateId),
    ) ?? []
  const blocked = cases.find(
    (test) =>
      test.after !== "passed" ||
      test.before !==
        (test.category === "security" ? "assertion_failed" : "passed"),
  )
  if (blocked) return { ...step, detail: blocked.reason, status: "attention" }
  if (["failed", "inconclusive", "stale"].includes(comparison?.status ?? ""))
    return {
      ...step,
      detail:
        comparison?.status === "stale"
          ? "材料已变化，需要重新验证"
          : candidateId && cases.length
            ? "该项用例通过，关联补丁仍有其他验证未通过"
            : "验证未通过或证据不足，请查看具体结果",
      status: "attention",
    }
  if (syntax === "failed" || ["failed", "needs_review"].includes(rescan ?? ""))
    return {
      ...step,
      detail:
        syntax === "failed"
          ? "补丁语法检查未通过"
          : "CodeQL 复扫仍有待处理告警",
      status: "attention",
    }
  if (comparison?.status === "passed")
    return { ...step, detail: "所列安全与功能测试通过", status: "done" }
  return step
}
