import { createFileRoute, Outlet } from "@tanstack/react-router"
import { FileText, Monitor, Terminal } from "lucide-react"
export const Route = createFileRoute("/_layout")({
  component: Layout,
})
function Layout() {
  return (
    <div className="audit-shell">
      <aside className="audit-sidebar">
        <a href="/" className="audit-brand">
          <span>
            <Terminal size={22} />
          </span>
          AI Code Audit
        </a>
        <a href="/" className="audit-nav">
          <FileText size={20} />
          审计任务
        </a>
        <footer>
          <p>
            <Monitor size={19} />
            本地工作台
          </p>
        </footer>
      </aside>
      <main className="audit-content">
        <Outlet />
      </main>
    </div>
  )
}
