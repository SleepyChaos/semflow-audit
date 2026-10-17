import {
  createFileRoute,
  Link,
  Outlet,
  useLocation,
} from "@tanstack/react-router"
import { PanelLeftClose, PanelLeftOpen, Plus } from "lucide-react"
import { useEffect, useState } from "react"
import { useTheme } from "@/components/theme-provider"
import { AppSidebar } from "@/features/shell/AppSidebar"
import { EnvironmentDrawer } from "@/features/shell/EnvironmentDrawer"
export const Route = createFileRoute("/_layout")({ component: Layout })
function Layout() {
  const [environmentOpen, setEnvironmentOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem("semflow-sidebar-collapsed") === "true",
  )
  useEffect(() => {
    localStorage.setItem("semflow-sidebar-collapsed", String(sidebarCollapsed))
  }, [sidebarCollapsed])
  const { setTheme } = useTheme()
  useEffect(() => {
    setTheme("light")
  }, [setTheme])
  const location = useLocation()
  const section = location.pathname.startsWith("/audits")
    ? "审计任务"
    : location.pathname === "/rules"
      ? "规则库"
      : location.pathname === "/knowledge"
        ? "知识库"
        : "总览"
  return (
    <div className="audit-shell" data-sidebar-collapsed={sidebarCollapsed}>
      <AppSidebar onEnvironment={() => setEnvironmentOpen(true)} />
      <div className="workspace-body">
        <div className="workspace-toolbar">
          <div className="workspace-toolbar-start">
            <button
              type="button"
              className="sidebar-toggle"
              aria-label={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
              title={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
              aria-expanded={!sidebarCollapsed}
              aria-controls="workspace-sidebar"
              onClick={() => setSidebarCollapsed((value) => !value)}
            >
              {sidebarCollapsed ? (
                <PanelLeftOpen size={19} />
              ) : (
                <PanelLeftClose size={19} />
              )}
            </button>
            <div className="breadcrumb">
              <Link to="/">工作台</Link>
              <span>/</span>
              <span>{section}</span>
            </div>
          </div>
          <div className="toolbar-actions">
            <span className="workspace-edition">独立工作台</span>
            <Link to="/audits/new" className="button-link outline">
              <Plus size={15} />
              新建审计
            </Link>
          </div>
        </div>
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
