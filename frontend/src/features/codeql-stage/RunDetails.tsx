import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Download, RotateCcw } from "lucide-react"
import { toast } from "sonner"
import { type AuditRun, downloadSarif, getLogs, retryRun } from "@/api/audits"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { FindingDetails } from "./FindingDetails"
const phases: Record<string, string> = {
  queued: "等待后台执行",
  database: "正在建立 CodeQL 数据库",
  scan: "正在运行漏洞查询",
  parse: "正在保存告警证据",
  completed: "静态扫描完成",
}
export function RunDetails({
  run,
  onCreated,
}: {
  run: AuditRun
  onCreated: (id: string) => void
}) {
  const [findingId, setFindingId] = useState<string | null>(null)
  const cache = useQueryClient()
  const logs = useQuery({
    queryKey: ["logs", run.id],
    queryFn: () => getLogs(run.id),
    refetchInterval: run.status === "running" ? 3000 : false,
  })
  const retry = useMutation({
    mutationFn: () => retryRun(run.id),
    onSuccess: async (next) => {
      await cache.invalidateQueries({ queryKey: ["audits"] })
      onCreated(next.id)
    },
    onError: (error: Error) => toast.error(error.message),
  })
  const finding = run.findings.find((item) => item.id === findingId)
  return (
    <section className="detail-panel">
      <header className="detail-heading">
        <div>
          <h2>{run.project_name}</h2>
          <p>{phases[run.phase] ?? run.phase}</p>
        </div>
        {run.status === "completed" ? (
          <Button
            variant="outline"
            onClick={() =>
              downloadSarif(run.id).catch((error: Error) =>
                toast.error(error.message),
              )
            }
          >
            <Download data-icon="inline-start" />
            下载 SARIF
          </Button>
        ) : null}
        {run.status === "failed" ? (
          <Button
            variant="outline"
            disabled={retry.isPending}
            onClick={() => retry.mutate()}
          >
            <RotateCcw data-icon="inline-start" />
            创建重试任务
          </Button>
        ) : null}
      </header>
      <Tabs defaultValue="codeql">
        <TabsList>
          <TabsTrigger value="codeql">CodeQL 审计</TabsTrigger>
          <TabsTrigger value="ai">AI 复审</TabsTrigger>
          <TabsTrigger value="repair">修复与报告</TabsTrigger>
          <TabsTrigger value="rag">RAG 规则</TabsTrigger>
        </TabsList>
        <TabsContent value="codeql">
          {run.error ? (
            <Alert variant="destructive">
              <AlertTitle>审计未完成</AlertTitle>
              <AlertDescription>{run.error}</AlertDescription>
            </Alert>
          ) : null}
          <dl className="run-metadata">
            <div>
              <dt>代码快照</dt>
              <dd>{run.snapshot_hash.slice(0, 16)}</dd>
            </div>
            <div>
              <dt>CodeQL</dt>
              <dd>{run.codeql_version ?? "待执行"}</dd>
            </div>
            <div>
              <dt>查询包</dt>
              <dd>{run.query_pack}</dd>
            </div>
          </dl>
          {run.coverage.unscanned_languages?.length ? (
            <Alert>
              <AlertTitle>覆盖范围</AlertTitle>
              <AlertDescription>
                本次未扫描：{run.coverage.unscanned_languages.join("、")}
              </AlertDescription>
            </Alert>
          ) : null}
          {run.status === "completed" && !run.findings.length ? (
            <p className="py-5">本次规则集未报告告警，不代表代码不存在漏洞。</p>
          ) : null}
          <div className="findings-list">
            {run.findings.map((item) => (
              <Button
                key={item.id}
                variant={findingId === item.id ? "secondary" : "ghost"}
                className="finding-button"
                onClick={() => setFindingId(item.id)}
              >
                {item.rule} · {item.locations[0].file}:{item.locations[0].line}
              </Button>
            ))}
          </div>
          {finding ? (
            <FindingDetails key={finding.id} finding={finding} runId={run.id} />
          ) : null}
          <details className="execution-log">
            <summary>执行日志</summary>
            <pre>
              {logs.error
                ? logs.error.message
                : logs.data?.text || "暂无执行日志"}
            </pre>
          </details>
        </TabsContent>
        {["ai", "repair", "rag"].map((value) => (
          <TabsContent key={value} value={value}>
            <Alert>
              <AlertTitle>该阶段尚未接入</AlertTitle>
              <AlertDescription>
                首版正在验证上传与真实 CodeQL 扫描链路，该阶段没有产生审计结论。
              </AlertDescription>
            </Alert>
          </TabsContent>
        ))}
      </Tabs>
    </section>
  )
}
