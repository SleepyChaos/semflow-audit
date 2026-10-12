import { useQuery } from "@tanstack/react-query"
import { CircleAlert, CircleCheck, LoaderCircle, RefreshCw } from "lucide-react"
import { useState } from "react"
import { getEnvironment, getRuns } from "@/api/audits"
import { getStages } from "@/api/stages"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { RunDetails } from "@/features/codeql-stage/RunDetails"
import { UploadForm } from "@/features/upload/UploadForm"
import { Pipeline } from "./Pipeline"
import { RunList } from "./RunList"
export function Workbench() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [activeStage, setActiveStage] = useState("codeql")
  const selectRun = (id: string) => {
    setSelectedId(id)
    setActiveStage("codeql")
  }
  const history = useQuery({
    queryKey: ["stages", selectedId],
    queryFn: () => getStages(selectedId!),
    enabled: Boolean(selectedId),
    refetchInterval: (query) =>
      query.state.data?.some((item) =>
        ["queued", "running"].includes(item.status),
      )
        ? 2500
        : false,
  })
  const runs = useQuery({
    queryKey: ["audits"],
    queryFn: getRuns,
    refetchInterval: (query) =>
      query.state.data?.some((run) =>
        ["queued", "running"].includes(run.status),
      )
        ? 2500
        : false,
  })
  const environment = useQuery({
    queryKey: ["environment"],
    queryFn: getEnvironment,
    refetchInterval: 15000,
  })
  const selected = runs.data?.find((run) => run.id === selectedId)
  const ready = Boolean(
    environment.data?.codeql_version &&
      environment.data.query_packs_present &&
      environment.data.queue_available,
  )
  return (
    <div className="workbench-grid">
      <div className="workbench-main">
        <header className="workbench-header">
          <div>
            <h1>审计工作台</h1>
            <p>上传代码，开始一次可追溯的审计</p>
          </div>
          <Button
            variant="outline"
            onClick={() => {
              runs.refetch()
              environment.refetch()
            }}
          >
            <RefreshCw data-icon="inline-start" />
            刷新
          </Button>
        </header>
        <Pipeline
          completed={selected?.status === "completed"}
          active={activeStage}
          history={history.data ?? []}
          onSelect={selected ? setActiveStage : undefined}
        />
        <UploadForm onCreated={selectRun} />
        {runs.error ? (
          <Alert variant="destructive">
            <AlertTitle>无法读取审计任务</AlertTitle>
            <AlertDescription>{runs.error.message}</AlertDescription>
          </Alert>
        ) : null}
        {runs.isPending ? (
          <Skeleton className="h-40" />
        ) : (
          <RunList
            runs={runs.data ?? []}
            onSelect={selectRun}
            selected={selectedId}
          />
        )}
        {selected ? (
          <RunDetails
            key={selected.id}
            run={selected}
            activeStage={activeStage}
            onStageChange={setActiveStage}
            onCreated={selectRun}
          />
        ) : null}
      </div>
      <aside className="environment-panel">
        <h2>执行环境</h2>
        <div className="environment-status">
          {environment.isPending ? (
            <LoaderCircle className="animate-spin" />
          ) : ready ? (
            <CircleCheck />
          ) : (
            <CircleAlert />
          )}
          <div>
            <strong>CodeQL</strong>
            <p>
              {environment.isPending
                ? "检查中"
                : environment.error
                  ? "连接失败"
                  : (environment.data?.codeql_version ?? "不可用")}
            </p>
          </div>
        </div>
        {environment.data ? (
          <dl className="environment-info">
            <dt>查询包</dt>
            <dd>
              {environment.data.query_packs_present ? "已安装" : "未安装"}
            </dd>
            <dt>任务队列</dt>
            <dd>{environment.data.queue_available ? "已连接" : "未连接"}</dd>
          </dl>
        ) : null}
        {!ready && !environment.isPending ? (
          <p className="text-sm text-muted-foreground">
            请检查执行环境；扫描失败会保存错误记录。
          </p>
        ) : null}
      </aside>
    </div>
  )
}
