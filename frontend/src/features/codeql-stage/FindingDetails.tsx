import { useQuery } from "@tanstack/react-query"
import { getSource, type Finding } from "@/api/audits"
export function FindingDetails({
  finding,
  runId,
}: {
  finding: Finding
  runId: string
}) {
  const location = finding.locations[0]
  const source = useQuery({
    queryKey: ["source", runId, location],
    queryFn: () => getSource(runId, location),
  })
  return (
    <article className="finding-detail">
      <h3>{finding.rule}</h3>
      <p>{finding.message}</p>
      <p className="text-sm text-muted-foreground">
        {location.file}:{location.line} · 原始静态告警，尚未 AI 复审
      </p>
      {source.isPending ? (
        <p>正在获取源码…</p>
      ) : source.error ? (
        <p role="alert">{source.error.message}</p>
      ) : (
        <pre className="source-code">
          <code>
            {source.data.lines
              .map(
                (line, index) =>
                  `${String(source.data.start_line + index).padStart(4)}  ${line}`,
              )
              .join("\n")}
          </code>
        </pre>
      )}
      {finding.code_flows.length ? (
        <>
          <h4>CodeQL 路径证据</h4>
          {finding.code_flows.map((flow, index) => (
            <ol key={`${finding.id}-${index}`} className="flow-list">
              {flow.map((step, position) => (
                <li key={`${step.file}:${step.line}:${position}`}>
                  {step.file}:{step.line}
                </li>
              ))}
            </ol>
          ))}
        </>
      ) : (
        <p className="text-sm text-muted-foreground">
          该查询未提供数据流路径。
        </p>
      )}
    </article>
  )
}
