import { Link } from "@tanstack/react-router"
import type { RuleVersion } from "@/api/stages"
import { Badge } from "@/components/ui/badge"
import { ProjectReplayReview } from "./ProjectReplayReview"
import { RuleActions } from "./RuleActions"
import { RuleCodeView } from "./RuleCodeView"
import { RuleValidationSummary } from "./RuleValidationSummary"
export function RuleCard({
  rule,
  awaiting,
  embedded = false,
}: {
  rule: RuleVersion
  awaiting: boolean
  embedded?: boolean
}) {
  return (
    <article className="candidate-card rule-card" id={`rule-${rule.id}`}>
      <header>
        <h4>{rule.title}</h4>
        <Badge variant="outline">
          {(
            {
              draft: "草稿",
              validated: "验收通过",
              published: "已发布",
              retired: "已停用",
              failed: "验收失败",
            } as Record<string, string>
          )[rule.status] ?? rule.status}
        </Badge>
      </header>
      <p>
        {(
          {
            review_anchor: "复审锚点",
            vulnerability_detector: "漏洞检测规则",
            framework_model: "框架建模",
          } as Record<string, string>
        )[rule.purpose] ?? rule.purpose}{" "}
        · 版本 {rule.id.slice(0, 8)}
      </p>
      <RuleCodeView key={rule.id} query={rule.query} modules={rule.modules} />
      <RuleValidationSummary rule={rule} />
      {!embedded && (
        <div className="stage-row">
          <Link
            className="text-action"
            to="/audits/$auditId"
            params={{ auditId: rule.audit_id }}
            search={{ stage: "rules" }}
          >
            来源审计任务 →
          </Link>
          {rule.status === "published" && (
            <Link
              className="button-link outline"
              to="/audits/new"
              search={{ ruleId: rule.id }}
            >
              用于新审计
            </Link>
          )}
        </div>
      )}
      <details>
        <summary>RAG 检索引用</summary>
        {rule.retrieval.map((item) => (
          <article key={item.id}>
            <h4>{item.title}</h4>
            <p>
              {item.source} · {item.version.slice(0, 16)}
            </p>
            <pre className="source-code">{item.content}</pre>
          </article>
        ))}
      </details>
      <details>
        <summary>正反例与预期位置（需要核实覆盖与语义）</summary>
        <pre className="source-code">
          {JSON.stringify(rule.fixtures, null, 2)}
        </pre>
      </details>
      <p>
        独立测试集：{rule.holdout_id ?? "未选择"}
        。自生成样本通过与独立验收分别记录。
      </p>
      <details>
        <summary>规则验收与覆盖分析</summary>
        <pre className="source-code">
          {JSON.stringify(rule.validation, null, 2)}
        </pre>
      </details>
      {!embedded && (
        <details>
          <summary>项目复测与根因确认</summary>
          <ProjectReplayReview rule={rule} />
        </details>
      )}
      {!embedded && (
        <div className="stage-row">
          <RuleActions rule={rule} awaiting={awaiting} />
        </div>
      )}
      <p>样本通过不代表真实项目准确率；新扫描需显式选择发布版本。</p>
    </article>
  )
}
