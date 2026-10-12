import { useQuery } from "@tanstack/react-query"
import { Link, useLocation } from "@tanstack/react-router"
import {
  BookOpen,
  ChevronRight,
  Database,
  FileText,
  House,
  Library,
  Search,
  SquareTerminal,
  Wrench,
} from "lucide-react"
import { getEnvironment } from "@/api/audits"
import { useAudit } from "@/features/audit-task/useAuditData"
import { auditStages, languageName, normalizeStage } from "./navigation"

const icons = {
  scan: Search,
  review: FileText,
  repair: Wrench,
  rules: BookOpen,
}
export function AppSidebar({ onEnvironment }: { onEnvironment: () => void }) {
  const location = useLocation()
  const match = location.pathname.match(/^\/audits\/([^/]+)\/?$/)
  const auditId =
    match && match[1] !== "new" ? decodeURIComponent(match[1]) : null
  const audit = useAudit(auditId)
  const run = audit.data
  const stage = normalizeStage(location.search.stage)
  const environment = useQuery({
    queryKey: ["environment"],
    queryFn: getEnvironment,
    refetchInterval: 15000,
    retry: 1,
  })
  const ready = Boolean(
    environment.data?.codeql_version &&
      environment.data.query_packs_present &&
      environment.data.queue_available,
  )
  return (
    <aside className="audit-sidebar">
      <Link to="/" className="audit-brand">
        <SquareTerminal size={25} />
        <span>Semflow Audit</span>
      </Link>
      <nav aria-label="主导航" className="sidebar-navigation">
        <div className="nav-group">
          <p className="nav-caption">工作台</p>
          <Link
            to="/"
            className="audit-nav"
            aria-current={location.pathname === "/" ? "page" : undefined}
          >
            <House size={18} />
            总览
          </Link>
          <Link
            to="/audits"
            className="audit-nav"
            aria-current={
              location.pathname.startsWith("/audits") && !auditId
                ? "page"
                : undefined
            }
          >
            <FileText size={18} />
            审计任务
          </Link>
        </div>
        <div className="nav-group">
          <p className="nav-caption">当前审计</p>
          {auditId ? (
            <>
              <div className="sidebar-project">
                <strong title={run?.project_name}>
                  {run?.project_name ?? auditId}
                </strong>
                <span>{run ? languageName(run.language) : "正在读取项目"}</span>
              </div>
              {auditStages.map((item) => {
                const Icon = icons[item.id]
                return (
                  <Link
                    key={item.id}
                    to="/audits/$auditId"
                    params={{ auditId }}
                    search={{ stage: item.id }}
                    className="audit-nav stage-nav"
                    aria-current={stage === item.id ? "page" : undefined}
                  >
                    <Icon size={18} />
                    {item.title}
                  </Link>
                )
              })}
            </>
          ) : (
            <Link to="/audits" className="select-task-link">
              选择一个审计任务
              <ChevronRight size={15} />
            </Link>
          )}
        </div>
        <div className="nav-group">
          <p className="nav-caption">管理</p>
          <Link
            to="/rules"
            className="audit-nav"
            aria-current={location.pathname === "/rules" ? "page" : undefined}
          >
            <Library size={18} />
            规则库
          </Link>
          <Link
            to="/knowledge"
            className="audit-nav"
            aria-current={
              location.pathname === "/knowledge" ? "page" : undefined
            }
          >
            <Database size={18} />
            知识库
          </Link>
        </div>
      </nav>
      <button
        type="button"
        className="environment-trigger"
        onClick={onEnvironment}
      >
        <span className={ready ? "status-dot ready" : "status-dot"} />
        {environment.isPending
          ? "正在检查环境"
          : environment.error
            ? "环境连接失败"
            : ready
              ? "本地环境已连接"
              : "执行环境待配置"}
        <ChevronRight size={14} />
      </button>
    </aside>
  )
}
