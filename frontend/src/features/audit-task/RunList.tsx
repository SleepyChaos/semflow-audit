import { FileText } from "lucide-react"
import { type AuditRun } from "@/api/audits"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Button } from "@/components/ui/button"
const statuses: Record<string, string> = {
  queued: "等待执行",
  running: "审计中",
  completed: "已完成",
  failed: "失败",
}
export function RunList({
  runs,
  onSelect,
  selected,
}: {
  runs: AuditRun[]
  onSelect: (id: string) => void
  selected: string | null
}) {
  return (
    <section className="task-panel">
      <h2>审计任务</h2>
      <Table>
        <TableHeader>
          <TableRow>
            {["项目", "语言", "状态", "发现", "创建时间"].map((label) => (
              <TableHead key={label}>{label}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.map((run) => (
            <TableRow
              key={run.id}
              data-state={selected === run.id ? "selected" : undefined}
            >
              <TableCell>
                <Button variant="link" onClick={() => onSelect(run.id)}>
                  {run.project_name}
                </Button>
              </TableCell>
              <TableCell>
                {run.language === "python" ? "Python" : "JS / TS"}
              </TableCell>
              <TableCell>
                <Badge
                  variant={
                    run.status === "failed" ? "destructive" : "secondary"
                  }
                >
                  {statuses[run.status] ?? run.status}
                </Badge>
              </TableCell>
              <TableCell>
                {run.status === "completed" ? run.findings.length : "—"}
              </TableCell>
              <TableCell>
                {new Date(run.created_at).toLocaleString("zh-CN")}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {!runs.length ? (
        <Empty>
          <EmptyHeader>
            <EmptyMedia>
              <FileText size={36} />
            </EmptyMedia>
            <EmptyTitle>暂无审计任务</EmptyTitle>
            <EmptyDescription>开始上传你的第一个项目。</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : null}
    </section>
  )
}
