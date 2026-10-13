import { ChevronRight } from "lucide-react"
import { useState } from "react"
import type { AuditRun } from "@/api/audits"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { labelStatus } from "@/features/stages/stage-labels"
import { codeqlStatus } from "./discovery-state"
import { FindingDetails } from "./FindingDetails"

export function CodeqlResults({ run }: { run: AuditRun }) {
  const [findingId, setFindingId] = useState<string | null>(null)
  const finding = run.findings.find((item) => item.id === findingId)
  const status = codeqlStatus(run)
  return (
    <Card className="discovery-engine" aria-label="CodeQL 静态分析">
      <CardHeader>
        <div className="discovery-heading">
          <CardTitle>
            <h3>CodeQL 静态分析</h3>
          </CardTitle>
          <Badge variant={status === "failed" ? "destructive" : "secondary"}>
            {status === "completed" ? "扫描完成" : labelStatus(status)}
          </Badge>
        </div>
        <CardDescription>
          已保存 {run.findings.length} 条静态告警 · 点击条目查看源码与路径证据
        </CardDescription>
      </CardHeader>
      <CardContent
        className="discovery-scroll"
        role="region"
        aria-label="CodeQL 结果滚动区域"
        tabIndex={0}
      >
        {run.error ? (
          <Alert variant="destructive">
            <AlertTitle>CodeQL 分支未完成</AlertTitle>
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
            <AlertTitle>语言覆盖范围</AlertTitle>
            <AlertDescription>
              本次未扫描：{run.coverage.unscanned_languages.join("、")}
            </AlertDescription>
          </Alert>
        ) : null}
        {!run.findings.length ? (
          <p className="page-note">
            {status === "completed"
              ? "本次规则集未报告告警，不代表代码不存在漏洞。"
              : status === "failed" || status === "cancelled"
                ? "扫描未完成，没有可展示的静态告警。"
                : "等待静态扫描产出告警…"}
          </p>
        ) : null}
        <div className="findings-list">
          {run.findings.map((item) => (
            <Button
              type="button"
              key={item.id}
              variant={findingId === item.id ? "default" : "secondary"}
              className="finding-button"
              aria-pressed={findingId === item.id}
              aria-controls={`finding-detail-${run.id}`}
              onClick={() => setFindingId(item.id)}
            >
              <span className="finding-label">
                <strong>{item.rule}</strong>
                <span>
                  {item.locations[0]?.file ?? "位置待核实"}:
                  {item.locations[0]?.line ?? "—"}
                </span>
              </span>
              <span className="finding-open">查看证据</span>
              <ChevronRight data-icon="inline-end" />
            </Button>
          ))}
        </div>
        <div id={`finding-detail-${run.id}`}>
          {finding ? (
            <FindingDetails key={finding.id} finding={finding} runId={run.id} />
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}
