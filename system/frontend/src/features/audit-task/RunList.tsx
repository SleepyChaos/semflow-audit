import { Link } from "@tanstack/react-router"
import type { AuditRun } from "@/api/audits"
import { getTaskAction, runStatuses } from "./task-summary"
import { useRunSummaries } from "./useRunSummaries"
export function RunList({
  runs,
  onSelect,
  selected,
}: {
  runs: AuditRun[]
  onSelect?: (id: string) => void
  selected?: string | null
}) {
  const summaries = useRunSummaries(runs)
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            {[
              "项目",
              "语言",
              "扫描状态",
              "静态告警",
              "AI 候选",
              "人工确认",
              "创建时间",
              "操作",
            ].map((label) => (
              <th key={label}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {summaries.map(({ run, query, summary }) => {
            const unknown = query.isError ? "无法读取" : "读取中",
              action = getTaskAction(run, query.data)
            const staticCount =
              run.coverage.dual_engine?.codeql?.status === "completed" ||
              run.status === "completed"
                ? run.findings.length
                : "—"
            return (
              <tr
                key={run.id}
                data-state={selected === run.id ? "selected" : undefined}
              >
                <td className="project-cell">
                  {onSelect ? (
                    <button type="button" onClick={() => onSelect(run.id)}>
                      {run.project_name}
                    </button>
                  ) : (
                    <Link
                      to="/audits/$auditId"
                      params={{ auditId: run.id }}
                      search={{ stage: "scan" }}
                    >
                      {run.project_name}
                    </Link>
                  )}
                  <small>{run.id.slice(0, 8)}</small>
                </td>
                <td>{run.language === "python" ? "Python" : "JS / TS"}</td>
                <td>
                  <span
                    className={
                      run.status === "failed"
                        ? "status-label error"
                        : "status-label"
                    }
                  >
                    {runStatuses[run.status] ?? run.status}
                  </span>
                </td>
                <td data-testid="static-count">{staticCount}</td>
                <td data-testid="ai-count">
                  {summary?.aiCandidates ?? unknown}
                </td>
                <td data-testid="confirmed-count">
                  {summary?.confirmed ?? unknown}
                </td>
                <td>{new Date(run.created_at).toLocaleDateString("zh-CN")}</td>
                <td>
                  {action && (
                    <Link
                      className="text-action"
                      to="/audits/$auditId"
                      params={{ auditId: run.id }}
                      search={{ stage: action.stage }}
                    >
                      {action.label} →
                    </Link>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {!runs.length && (
        <div className="empty-state">
          <h2>暂无审计任务</h2>
          <p>上传一个源码 ZIP，开始扫描和复核。</p>
          <Link className="button-link" to="/audits/new">
            新建审计
          </Link>
        </div>
      )}
    </div>
  )
}
