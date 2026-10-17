import { useQuery } from "@tanstack/react-query"
import { Link, useLocation } from "@tanstack/react-router"
import {
  BookOpen,
  ChevronRight,
  Database,
  FileText,
  FolderCode,
  House,
  Library,
  Search,
  ShieldCheck,
  SquareTerminal,
  Wrench,
} from "lucide-react"
import { getEnvironment } from "@/api/audits"
import { useAudit } from "@/features/audit-task/useAuditData"
import { auditStages, languageName, normalizeStage } from "./navigation"

const icons = {
  scan: Search,
  review: ShieldCheck,
  report: FileText,
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
  const environmentLabel = environment.isPending
    ? "正在检查环境"
    : environment.error
      ? "环境连接失败"
      : ready
        ? "本地环境已连接"
        : "执行环境待配置"
  return (
    <aside
      id="workspace-sidebar"
      className="audit-sidebar"
      aria-label="工作台侧边栏"
    >
      <Link
        to="/"
        className="audit-brand"
        aria-label="Semflow Audit 工作台"
        title="Semflow Audit 工作台"
      >
        <SquareTerminal size={25} />
        <span>Semflow Audit</span>
      </Link>
      <nav aria-label="主导航" className="sidebar-navigation">
        <div className="nav-group">
          <p className="nav-caption">工作台</p>
          <Link
            to="/"
            className="audit-nav"
            aria-label="总览"
            title="总览"
            aria-current={location.pathname === "/" ? "page" : undefined}
          >
            <House size={18} />
            <span className="nav-label">总览</span>
          </Link>
          <Link
            to="/audits"
            className="audit-nav"
            aria-label="审计任务"
            title="审计任务"
            aria-current={
              location.pathname.startsWith("/audits") && !auditId
                ? "page"
                : undefined
            }
          >
            <FileText size={18} />
            <span className="nav-label">审计任务</span>
          </Link>
        </div>
        <div className="nav-group">
          {auditId ? (
            <>
              <Link
                to="/audits/$auditId"
                params={{ auditId }}
                search={{ stage }}
                className="sidebar-project"
                aria-label={`当前审计：${run?.project_name ?? auditId}`}
                title={`${run?.project_name ?? auditId}${run ? ` · ${languageName(run.language)}` : ""}`}
              >
                <FolderCode
                  size={22}
                  className="sidebar-project-icon"
                  aria-hidden="true"
                />
                <strong title={run?.project_name}>
                  {run?.project_name ?? auditId}
                </strong>
                <span>{run ? languageName(run.language) : "正在读取项目"}</span>
              </Link>
              {auditStages.map((item) => {
                const Icon = icons[item.id]
                return (
                  <Link
                    key={item.id}
                    to="/audits/$auditId"
                    params={{ auditId }}
                    search={{ stage: item.id }}
                    className="audit-nav stage-nav"
                    aria-label={item.title}
                    title={item.title}
                    aria-current={stage === item.id ? "page" : undefined}
                  >
                    <Icon size={18} />
                    <span className="nav-label">{item.title}</span>
                  </Link>
                )
              })}
            </>
          ) : (
            <Link
              to="/audits"
              className="select-task-link"
              aria-label="选择一个审计任务"
              title="选择一个审计任务"
            >
              <span className="nav-label">选择一个审计任务</span>
              <ChevronRight size={15} />
            </Link>
          )}
        </div>
        <div className="nav-group">
          <p className="nav-caption">管理</p>
          <Link
            to="/rules"
            className="audit-nav"
            aria-label="规则库"
            title="规则库"
            aria-current={location.pathname === "/rules" ? "page" : undefined}
          >
            <Library size={18} />
            <span className="nav-label">规则库</span>
          </Link>
          <Link
            to="/knowledge"
            className="audit-nav"
            aria-label="知识库"
            title="知识库"
            aria-current={
              location.pathname === "/knowledge" ? "page" : undefined
            }
          >
            <Database size={18} />
            <span className="nav-label">知识库</span>
          </Link>
        </div>
      </nav>
      <button
        type="button"
        className="environment-trigger"
        onClick={onEnvironment}
        aria-label={environmentLabel}
        title={environmentLabel}
      >
        <span className={ready ? "status-dot ready" : "status-dot"} />
        <span className="nav-label">{environmentLabel}</span>
        <ChevronRight size={14} />
      </button>
    </aside>
  )
}
