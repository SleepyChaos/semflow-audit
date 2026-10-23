import type { RepairRecord, RuleVersion, StageRun } from "@/api/stages"
import { repairProgressState } from "@/features/repair/repair-progress"
import { labelPhase } from "./stage-labels"
import type { WorkflowStep } from "./WorkflowSteps"

export function repairProgress(
  stages: StageRun[],
  records: RepairRecord[],
): WorkflowStep[] {
  return repairProgressState(stages, records).steps
}
export function ruleProgress(
  stages: StageRun[],
  rules: RuleVersion[],
): WorkflowStep[] {
  const latest = [...stages]
    .filter((row) => row.kind === "rule")
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
  const rule = rules.find((row) => row.stage_id === latest?.id)
  const running = latest && ["queued", "running"].includes(latest.status)
  const generating = running && !rule
  const validating = running && Boolean(rule)
  const valid = rule && ["validated", "published"].includes(rule.status)
  const targetSaved = Boolean(rule || running || latest?.inputs.candidate_id)
  return [
    {
      title: "确定规则目标",
      detail: targetSaved ? "目标已保存" : "选择确认真实的漏洞",
      status: targetSaved ? "done" : "active",
    },
    {
      title: "检索与生成",
      detail: generating
        ? labelPhase(latest.phase)
        : rule
          ? "规则草稿已保存"
          : "自动检索参考资料与范例",
      status: generating
        ? "active"
        : latest?.status === "failed" && !rule
          ? "attention"
          : rule
            ? "done"
            : "waiting",
    },
    {
      title: "正反例与项目验收",
      detail: valid
        ? "全部发布门通过"
        : validating
          ? labelPhase(latest.phase)
          : latest?.status === "awaiting_confirmation"
            ? "确认开发样本后继续验收"
            : "查看验证结果与覆盖范围",
      statusLabel:
        latest?.status === "awaiting_confirmation" ? "待确认" : undefined,
      status: valid
        ? "done"
        : validating
          ? "active"
          : latest?.status === "awaiting_confirmation"
            ? "active"
            : rule && (rule.status === "failed" || latest?.status === "failed")
              ? "attention"
              : "waiting",
    },
    {
      title: "发布与复用",
      detail: rule?.status === "published" ? "可用于新审计" : "验收完成后发布",
      status:
        rule?.status === "published" ? "done" : valid ? "active" : "waiting",
    },
  ]
}
