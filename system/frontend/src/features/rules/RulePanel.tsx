import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import type { AuditRun } from "@/api/audits"
import { type Capabilities, getRules, type StageRun } from "@/api/stages"
import { StageHistory } from "@/features/stages/StageHistory"
import { labelPhase } from "@/features/stages/stage-labels"
import {
  type WorkflowStep,
  WorkflowSteps,
} from "@/features/stages/WorkflowSteps"
import { RuleCard } from "./RuleCard"
import { RuleGenerationForm } from "./RuleGenerationForm"
export function RulePanel({
  run,
  stages,
  capabilities,
}: {
  run: AuditRun
  stages: StageRun[]
  capabilities: Capabilities | undefined
}) {
  const busy = stages.some((s) => ["queued", "running"].includes(s.status)),
    rules = useQuery({
      queryKey: ["rules", run.language],
      queryFn: () => getRules(run.language),
      refetchInterval: busy ? 3000 : false,
    })
  const currentStage = [...stages].sort((a, b) =>
    (b.created_at ?? "").localeCompare(a.created_at ?? ""),
  )[0]
  const taskRules = (rules.data ?? [])
    .filter((rule) => rule.audit_id === run.id)
    .sort((a, b) => {
      const time = (stageId: string) =>
        stages.find((stage) => stage.id === stageId)?.created_at ?? ""
      return time(b.stage_id).localeCompare(time(a.stage_id))
    })
  const latestRule =
    taskRules.find((rule) => rule.stage_id === currentStage?.id) ?? taskRules[0]
  const failures = currentStage?.status === "failed" ? [currentStage] : []
  const steps: WorkflowStep[] = [
    {
      title: "确定规则目标",
      detail: latestRule ? "目标已保存" : "选择真实漏洞或明确需求",
      status: latestRule || busy ? "done" : "active",
    },
    {
      title: "检索与生成",
      detail: busy
        ? labelPhase(currentStage?.phase ?? "")
        : latestRule
          ? "规则草稿已产生"
          : "自动检索参考资料与范例",
      status: busy
        ? "active"
        : failures.length
          ? "attention"
          : latestRule
            ? "done"
            : "waiting",
    },
    {
      title: "正反例与项目验收",
      detail:
        latestRule?.status === "validated" || latestRule?.status === "published"
          ? "全部发布门通过"
          : latestRule
            ? "检查每项验收结果"
            : "编译、正反例、独立集、项目回扫",
      status:
        latestRule?.status === "validated" || latestRule?.status === "published"
          ? "done"
          : currentStage?.status === "awaiting_confirmation"
            ? "attention"
            : "waiting",
    },
    {
      title: "发布与复用",
      detail:
        latestRule?.status === "published"
          ? "可用于新审计"
          : "验收完成后显式发布",
      status:
        latestRule?.status === "published"
          ? "done"
          : latestRule?.status === "validated"
            ? "active"
            : "waiting",
    },
  ]
  return (
    <section className="stage-section downstream-workspace">
      <WorkflowSteps steps={steps} label="规则生成流程" />
      <p className="page-note">
        生成检测规则以补充扫描覆盖；各项验证和人工决定分别记录。
      </p>
      {failures.map((s) => (
        <div className="failure-notice" role="alert" key={s.id}>
          {String(s.error).includes("材料") ||
          JSON.stringify(s.result).includes("materials_missing") ? (
            <>
              <h3>缺少匹配版本的参考材料或规则范例</h3>
              <p>
                先导入对应语言和 CodeQL 库版本的 API
                资料、完整规则范例，然后在执行历史中新建重跑。
              </p>
              <Link
                className="text-action"
                to="/knowledge"
                search={{ auditId: run.id }}
              >
                补充知识材料
              </Link>
            </>
          ) : (
            <h3>规则执行失败</h3>
          )}
          <details>
            <summary>原始错误与执行记录</summary>
            <p>{s.error}</p>
            <pre className="source-code">
              {JSON.stringify(s.result, null, 2)}
            </pre>
          </details>
        </div>
      ))}
      <RuleGenerationForm run={run} capabilities={capabilities} busy={busy} />
      <div className="section-heading">
        <h3>本任务生成的规则</h3>
        <Link to="/rules">打开规则库 →</Link>
      </div>
      {rules.error ? (
        <p role="alert">{rules.error.message}</p>
      ) : rules.isPending ? (
        <p>正在读取规则…</p>
      ) : taskRules.length ? (
        taskRules.map((rule) => (
          <RuleCard
            key={rule.id}
            rule={rule}
            awaiting={stages.some(
              (s) =>
                s.id === rule.stage_id && s.status === "awaiting_confirmation",
            )}
          />
        ))
      ) : (
        <div className="downstream-empty">
          <h4>尚未生成检测规则</h4>
          <p>选择目标后开始生成，草稿、引用资料与验收结果会在这里更新。</p>
        </div>
      )}
      <details className="downstream-disclosure">
        <summary>后台执行历史</summary>
        <StageHistory stages={stages} />
      </details>
    </section>
  )
}
