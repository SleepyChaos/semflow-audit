import { Link } from "@tanstack/react-router"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { WorkspaceSelect } from "@/components/WorkspaceSelect"
import { PageHeader } from "@/features/shell/PageHeader"
import { RunList } from "./RunList"
import { useAudits } from "./useAuditData"
export function AuditListPage() {
  const audits = useAudits(),
    [search, setSearch] = useState(""),
    [language, setLanguage] = useState("all"),
    [status, setStatus] = useState("all")
  const runs = audits.data ?? [],
    filtered = runs.filter(
      (r) =>
        r.project_name.toLowerCase().includes(search.toLowerCase()) &&
        (language === "all" || r.language === language) &&
        (status === "all" || r.status === status),
    )
  return (
    <div className="page-stack">
      <PageHeader
        title="审计任务"
        description="管理源码扫描、候选复核和后续处理"
        actions={
          <Link to="/audits/new" className="button-link">
            新建审计
          </Link>
        }
      />
      <div className="filter-bar">
        <input
          aria-label="搜索项目"
          placeholder="搜索项目名称…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <WorkspaceSelect
          aria-label="筛选语言"
          value={language}
          onValueChange={setLanguage}
          options={[
            { value: "all", label: "所有语言" },
            { value: "python", label: "Python" },
            { value: "javascript", label: "JavaScript / TypeScript" },
          ]}
        />
        <WorkspaceSelect
          aria-label="筛选扫描状态"
          value={status}
          onValueChange={setStatus}
          options={[
            { value: "all", label: "所有扫描状态" },
            { value: "completed", label: "扫描完成" },
            { value: "running", label: "扫描中" },
            { value: "failed", label: "扫描失败" },
            { value: "queued", label: "等待扫描" },
            { value: "cancelled", label: "已取消" },
          ]}
        />
        <Button variant="outline" onClick={() => audits.refetch()}>
          刷新
        </Button>
      </div>
      {audits.isPending ? (
        <p role="status">正在读取任务…</p>
      ) : audits.error ? (
        <p role="alert">无法读取任务：{audits.error.message}</p>
      ) : runs.length && !filtered.length ? (
        <div className="empty-state">没有符合筛选条件的任务</div>
      ) : (
        <RunList runs={filtered} />
      )}
      <p className="page-note">
        静态告警来自 CodeQL；AI 候选需要复核，通过 AI
        复核或人工调整的分类用于后续流程。
      </p>
    </div>
  )
}
