import { useQueries, useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { useEffect, useState } from "react"
import { getRules, getStages } from "@/api/stages"
import { Button } from "@/components/ui/button"
import { WorkspaceSelect } from "@/components/WorkspaceSelect"
import { PageHeader } from "@/features/shell/PageHeader"
import { RuleCard } from "./RuleCard"
export function RulesPage({ ruleId }: { ruleId?: string }) {
  const [language, setLanguage] = useState("all"),
    [purpose, setPurpose] = useState("all"),
    [status, setStatus] = useState("all"),
    [search, setSearch] = useState("")
  const rules = useQuery({
    queryKey: ["rules", "all"],
    queryFn: () => getRules(),
    retry: 1,
    refetchInterval: 15000,
  })
  const sourceAudits = [
    ...new Set(
      (rules.data ?? [])
        .filter((rule) => rule.status === "draft" && !rule.fixtures_approved)
        .map((rule) => rule.audit_id),
    ),
  ]
  const stages = useQueries({
    queries: sourceAudits.map((auditId) => ({
      queryKey: ["stages", auditId],
      queryFn: () => getStages(auditId),
      refetchInterval: 15000,
    })),
  })
  const awaitingStages = new Set(
    stages.flatMap((query) =>
      (query.data ?? [])
        .filter((stage) => stage.status === "awaiting_confirmation")
        .map((stage) => stage.id),
    ),
  )
  useEffect(() => {
    if (ruleId && rules.data)
      document
        .getElementById(`rule-${ruleId}`)
        ?.scrollIntoView({ block: "start" })
  }, [ruleId, rules.data])
  const filtered =
    rules.data?.filter(
      (r) =>
        (language === "all" || r.language === language) &&
        (purpose === "all" || r.purpose === purpose) &&
        (status === "all" || r.status === status) &&
        r.title.toLowerCase().includes(search.toLowerCase()),
    ) ?? []
  return (
    <div className="page-stack">
      <PageHeader
        title="规则库"
        description="查看规则版本、真实验收与发布状态"
        actions={
          <Button variant="outline" onClick={() => rules.refetch()}>
            刷新
          </Button>
        }
      />
      <div className="filter-bar">
        <input
          aria-label="搜索规则"
          placeholder="搜索规则…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <WorkspaceSelect
          aria-label="规则语言"
          value={language}
          onValueChange={setLanguage}
          options={[
            { value: "all", label: "所有语言" },
            { value: "python", label: "Python" },
            { value: "javascript", label: "JS / TS" },
          ]}
        />
        <WorkspaceSelect
          aria-label="筛选规则用途"
          value={purpose}
          onValueChange={setPurpose}
          options={[
            { value: "all", label: "所有用途" },
            { value: "review_anchor", label: "复审锚点" },
            { value: "vulnerability_detector", label: "漏洞检测" },
            { value: "framework_model", label: "框架建模" },
          ]}
        />
        <WorkspaceSelect
          aria-label="规则状态"
          value={status}
          onValueChange={setStatus}
          options={[
            { value: "all", label: "所有状态" },
            { value: "draft", label: "草稿" },
            { value: "validated", label: "已验证" },
            { value: "published", label: "已发布" },
            { value: "retired", label: "已停用" },
          ]}
        />
      </div>
      {rules.isPending ? (
        <p>正在读取规则…</p>
      ) : rules.error ? (
        <p role="alert">规则读取失败：{rules.error.message}</p>
      ) : !filtered.length ? (
        <div className="empty-state">
          <h2>暂无符合条件的规则</h2>
          <p>进入一个审计任务的 RAG 规则页面，描述覆盖缺口并生成版本。</p>
          <Link to="/audits" className="button-link">
            选择审计任务
          </Link>
        </div>
      ) : (
        filtered.map((r) => (
          <RuleCard
            key={r.id}
            rule={r}
            awaiting={
              r.status === "draft" &&
              !r.fixtures_approved &&
              awaitingStages.has(r.stage_id)
            }
          />
        ))
      )}
    </div>
  )
}
