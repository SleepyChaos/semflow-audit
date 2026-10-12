import { useNavigate } from "@tanstack/react-router"
import {
  ArrowRight,
  Braces,
  FileCode2,
  GitBranch,
  Monitor,
  Moon,
  ScanSearch,
  Sparkles,
  Sun,
  Terminal,
  Wrench,
} from "lucide-react"
import { useTheme } from "@/components/theme-provider"
import { Button } from "@/components/ui/button"

const stages = [
  { icon: ScanSearch, label: "静态发现", detail: "CodeQL" },
  { icon: Sparkles, label: "证据复核", detail: "AI Review" },
  { icon: Wrench, label: "修复验证", detail: "Repair" },
  { icon: GitBranch, label: "规则生成", detail: "RAG" },
]

function AuditFlow() {
  return (
    <div
      className="welcome-flow"
      role="img"
      aria-label="源码快照连接四阶段审计：CodeQL 静态发现、AI 证据复核、修复验证、RAG 规则生成"
    >
      <div className="welcome-source">
        <Braces size={22} aria-hidden="true" />
        <span>源码快照</span>
        <span className="welcome-source-extension">.zip</span>
      </div>
      <div className="welcome-flow-branches" />
      <div className="welcome-flow-stages">
        {stages.map(({ icon: Icon, label, detail }, index) => (
          <div className="welcome-flow-stage" key={label}>
            <span className="welcome-step-number">0{index + 1}</span>
            <Icon size={23} aria-hidden="true" />
            <strong>{label}</strong>
            <span className="welcome-step-detail">{detail}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function Welcome() {
  const navigate = useNavigate()
  const { resolvedTheme, setTheme } = useTheme()
  const dark = resolvedTheme === "dark"
  const ThemeIcon = dark ? Sun : Moon

  return (
    <div className="welcome-page">
      <header className="welcome-header">
        <div className="welcome-brand">
          <span className="welcome-brand-mark">
            <Terminal size={22} aria-hidden="true" />
          </span>
          <span>SemFlow Audit</span>
        </div>
        <div className="welcome-header-actions">
          <span className="welcome-local-label">
            <Monitor size={16} aria-hidden="true" />
            本地工作台
          </span>
          <Button
            variant="ghost"
            size="icon-lg"
            aria-label={dark ? "切换到浅色主题" : "切换到深色主题"}
            onClick={() => setTheme(dark ? "light" : "dark")}
          >
            <ThemeIcon aria-hidden="true" />
          </Button>
        </div>
      </header>

      <main className="welcome-main">
        <section className="welcome-overview" aria-labelledby="welcome-title">
          <div>
            <h1 id="welcome-title">
              让代码中的风险，
              <br />
              <span>有迹可循。</span>
            </h1>
            <p className="welcome-overview-description">
              从静态分析到 AI 复核，连接发现、修复与规则生成。
              <br />
              每一步，都有源码证据与执行记录。
            </p>
          </div>
          <AuditFlow />
          <div className="welcome-language-note">
            <FileCode2 size={18} aria-hidden="true" />
            <span>Python · JavaScript · TypeScript</span>
          </div>
        </section>

        <section className="welcome-entry" aria-labelledby="entry-title">
          <div className="welcome-entry-content">
            <span className="welcome-entry-mark" aria-hidden="true">
              <Terminal size={27} />
            </span>
            <h2 id="entry-title">进入审计工作台</h2>
            <p className="welcome-entry-description">
              准备好你的代码包，
              <br />
              开始一次可追溯的代码审计。
            </p>
            <Button
              className="welcome-enter-button"
              size="lg"
              onClick={() => navigate({ to: "/" })}
            >
              进入工作台
              <ArrowRight data-icon="inline-end" aria-hidden="true" />
            </Button>
            <p className="welcome-entry-note">无需账号或密码，点击即可开始。</p>
            <div className="welcome-entry-guide">
              <div>
                <span>01</span>
                <p>上传 ZIP 格式的项目代码</p>
              </div>
              <div>
                <span>02</span>
                <p>查看发现、证据与审计进度</p>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="welcome-footer">
        <span>SemFlow Audit · 代码审计工作台</span>
        <span>CodeQL × AI</span>
      </footer>
    </div>
  )
}
