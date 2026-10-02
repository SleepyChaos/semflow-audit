import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"
import { FileText, LogOut, Monitor, Terminal } from "lucide-react"
import { Button } from "@/components/ui/button"
import { isLoggedIn } from "@/hooks/useAuth"
export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: () => {
    if (!isLoggedIn()) throw redirect({ to: "/login" })
  },
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
          <Button
            variant="ghost"
            onClick={() => {
              localStorage.removeItem("access_token")
              window.location.assign("/login")
            }}
          >
            <LogOut data-icon="inline-start" />
            退出登录
          </Button>
        </footer>
      </aside>
      <main className="audit-content">
        <Outlet />
      </main>
    </div>
  )
}
