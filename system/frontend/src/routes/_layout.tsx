import {
  createFileRoute,
  Link,
  Outlet,
  useLocation,
} from "@tanstack/react-router"
import { Plus } from "lucide-react"
import { useEffect, useState } from "react"
import { useTheme } from "@/components/theme-provider"
import { AppSidebar } from "@/features/shell/AppSidebar"
import { AuditExecutionLogs } from "@/features/shell/AuditExecutionLogs"
import { EnvironmentDrawer } from "@/features/shell/EnvironmentDrawer"
export const Route = createFileRoute("/_layout")({ component: Layout })
function Layout() {
  const [environmentOpen, setEnvironmentOpen] = useState(false)
  const { setTheme } = useTheme()
  useEffect(() => {
    setTheme("light")
  }, [setTheme])
  const location = useLocation()
  const auditMatch = location.pathname.match(/^\/audits\/([^/]+)\/?$/)
  const auditId =
    auditMatch && auditMatch[1] !== "new"
      ? decodeURIComponent(auditMatch[1])
      : null
  const section = location.pathname.startsWith("/audits")
    ? "审计任务"
    : location.pathname === "/rules"
      ? "规则库"
      : location.pathname === "/knowledge"
        ? "知识库"
        : "总览"
  return (
    <div className="audit-shell">
      <AppSidebar onEnvironment={() => setEnvironmentOpen(true)} />
      <div className="workspace-body">
        <div className="workspace-toolbar">
          <div className="breadcrumb">
            <Link to="/">工作台</Link>
            <span>/</span>
            <span>{section}</span>
          </div>
          <div className="toolbar-actions">
            <span className="workspace-edition">独立工作台</span>
            <Link to="/audits/new" className="button-link outline">
              <Plus size={15} />
              新建审计
            </Link>
          </div>
        </div>
        {auditId ? (
          <AuditExecutionLogs key={auditId} auditId={auditId} />
        ) : null}
        <main className="audit-content">
          <Outlet />
        </main>
      </div>
      <EnvironmentDrawer
        open={environmentOpen}
        onOpenChange={setEnvironmentOpen}
      />
    </div>
  )
}
