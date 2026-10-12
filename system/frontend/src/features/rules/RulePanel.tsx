import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import type { AuditRun } from "@/api/audits"
import { type Capabilities, getRules, type StageRun } from "@/api/stages"
import { StageHistory } from "@/features/stages/StageHistory"
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
  const failures = stages.filter((s) => s.status === "failed")
  return (
    <section className="stage-section">
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
      ) : (
        rules.data
          .filter((r) => r.audit_id === run.id)
          .map((rule) => (
            <RuleCard
              key={rule.id}
              rule={rule}
              awaiting={stages.some(
                (s) =>
                  s.id === rule.stage_id &&
                  s.status === "awaiting_confirmation",
              )}
            />
          ))
      )}
      <StageHistory stages={stages} />
    </section>
  )
}
