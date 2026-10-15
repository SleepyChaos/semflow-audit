import type { RepairRecord, RuleVersion, StageRun } from "@/api/stages"
import { labelPhase } from "./stage-labels"
import type { WorkflowStep } from "./WorkflowSteps"

export function repairProgress(
  stages: StageRun[],
  records: RepairRecord[],
): WorkflowStep[] {
  const latest = [...stages]
    .filter((row) => row.kind === "repair")
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
  const record = records.find((row) => row.stage_id === latest?.id)
  const running = latest && ["queued", "running"].includes(latest.status)
  const comparison = record?.comparison?.status
  return [
    {
      title: "选择修复目标",
      detail: record
        ? `${record.candidate_ids.length} 个目标已保存`
        : "在下方勾选真实漏洞",
      status: record || running ? "done" : "active",
    },
    {
      title: "生成补丁",
      detail: running
        ? labelPhase(latest.phase)
        : latest?.status === "failed"
          ? "本次生成失败"
          : record
            ? `${new Set(record.changes.map((row) => row.file)).size} 个文件有修改`
            : "保留原始源码快照",
      status: running
        ? "active"
        : latest?.status === "failed" || record?.status === "needs_review"
          ? "attention"
          : record
            ? "done"
            : "waiting",
    },
    {
      title: "前后验证",
      detail:
        comparison === "passed"
          ? "所列测试通过"
          : comparison === "failed"
            ? "验证未通过"
            : "对比漏洞复现与正常功能",
      status:
        comparison === "passed"
          ? "done"
          : ["failed", "inconclusive", "stale"].includes(comparison ?? "")
            ? "attention"
            : ["queued", "running"].includes(comparison ?? "")
              ? "active"
              : "waiting",
    },
    {
      title: "交付补丁",
      detail:
        record?.status === "accepted"
          ? "已接受，可下载"
          : "审阅 Diff 与验证范围",
      status:
        record?.status === "accepted"
          ? "done"
          : record?.acceptance_ready
            ? "active"
            : "waiting",
    },
  ]
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
