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
  const valid = rule && ["validated", "published"].includes(rule.status)
  return [
    {
      title: "确定规则目标",
      detail: rule || running ? "目标已保存" : "选择确认真实的漏洞",
      status: rule || running ? "done" : "active",
    },
    {
      title: "检索与生成",
      detail: running
        ? labelPhase(latest.phase)
        : rule
          ? "规则草稿已保存"
          : "自动检索参考资料与范例",
      status: running
        ? "active"
        : latest?.status === "failed"
          ? "attention"
          : rule
            ? "done"
            : "waiting",
    },
    {
      title: "正反例与项目验收",
      detail: valid ? "全部发布门通过" : "查看验证结果与覆盖范围",
      status: valid
        ? "done"
        : latest?.status === "awaiting_confirmation" ||
            rule?.status === "failed"
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
