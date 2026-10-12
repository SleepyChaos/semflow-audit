import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { useState } from "react"
import { toast } from "sonner"
import type { AuditRun } from "@/api/audits"
import {
  getCandidates,
  getRepairs,
  type StageRun,
  startStage,
} from "@/api/stages"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { uniqueCandidates } from "@/features/audit-task/task-summary"
import { StageHistory } from "@/features/stages/StageHistory"
import { AIReportPanel } from "./AIReportPanel"
import { RepairCard } from "./RepairCard"
import { VerificationSuitePanel } from "./VerificationSuitePanel"
export function RepairPanel({
  run,
  stages,
  modelReady,
}: {
  run: AuditRun
  stages: StageRun[]
  modelReady: boolean
}) {
  const [selected, setSelected] = useState<string[]>([]),
    [paths, setPaths] = useState(""),
    [profile, setProfile] = useState("syntax"),
    [rescan, setRescan] = useState(true),
    [suiteId, setSuiteId] = useState("")
  const cache = useQueryClient(),
    busy = stages.some((item) => ["queued", "running"].includes(item.status))
  const candidates = useQuery({
    queryKey: ["candidates", run.id],
    queryFn: () => getCandidates(run.id),
  })
  const repairs = useQuery({
    queryKey: ["repairs", run.id],
    queryFn: () => getRepairs(run.id),
    refetchInterval: busy ? 3000 : false,
  })
  const confirmed = uniqueCandidates(candidates.data ?? []).filter(
    (item) => item.status === "confirmed",
  )
  const start = useMutation({
    mutationFn: () =>
      startStage(run.id, "repair", {
        candidate_ids: selected.filter((id) =>
          confirmed.some((item) => item.id === id),
        ),
        allowed_paths: paths
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
        validation_profile: profile,
        rescan,
        ...(suiteId ? { verification_suite_id: suiteId } : {}),
      }),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  const selectedConfirmed = selected.filter((id) =>
    confirmed.some((item) => item.id === id),
  )
  const blocked = candidates.isPending
    ? "正在读取候选，请稍候"
    : candidates.error
      ? "候选读取失败，无法选择修复目标"
      : !confirmed.length
        ? "先确认缺陷"
        : !selectedConfirmed.length
          ? "请勾选要修复的已确认缺陷"
          : !modelReady
            ? "模型服务尚未配置"
            : busy
              ? "当前修复阶段正在执行"
              : null
  return (
    <section className="stage-section">
      <AIReportPanel auditId={run.id} modelReady={modelReady} />
      <h3>隔离修复</h3>
      <p className="page-note">
        已选择 {selectedConfirmed.length} 个已确认缺陷
      </p>
      <div className="stage-form">
        {confirmed.length ? (
          confirmed.map((item) => (
            <label
              className="stage-check"
              key={item.id}
              htmlFor={`repair-${run.id}-${item.id}`}
            >
              <Checkbox
                aria-label={item.title}
                id={`repair-${run.id}-${item.id}`}
                checked={selected.includes(item.id)}
                onCheckedChange={(checked) =>
                  setSelected(
                    checked
                      ? [...selected, item.id]
                      : selected.filter((id) => id !== item.id),
                  )
                }
              />
              {item.explanation?.title ?? item.title}
            </label>
          ))
        ) : (
          <div>
            <p>先确认缺陷</p>
            <p className="page-note">
              修复只针对人工确认的候选。请先核对源码和判断依据。
            </p>
            <Link
              className="text-action"
              to="/audits/$auditId"
              params={{ auditId: run.id }}
              search={{ stage: "review" }}
            >
              前往 AI 复审
            </Link>
          </div>
        )}
        <VerificationSuitePanel
          auditId={run.id}
          targets={selectedConfirmed}
          suiteId={suiteId}
          onSelect={setSuiteId}
          modelReady={modelReady}
          busy={busy}
          stages={stages}
        />
        <label>
          允许修改的关联文件（每行一个；源码证据文件自动加入）
          <textarea
            className="audit-textarea"
            value={paths}
            onChange={(event) => setPaths(event.target.value)}
          />
        </label>
        <Select value={profile} onValueChange={setProfile}>
          <SelectTrigger aria-label="补丁验证配置">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="syntax">隔离语法检查</SelectItem>
            {run.language === "python" ? (
              <SelectItem value="python_pytest">隔离 pytest</SelectItem>
            ) : (
              <SelectItem value="javascript_test">隔离 Node.js 测试</SelectItem>
            )}
          </SelectContent>
        </Select>
        <p className="action-hint">
          {profile === "syntax"
            ? "语法检查只检查代码能否解析。要验证正常业务和攻击输入，请准备项目依赖及测试，并选择项目测试。"
            : "项目测试需要镜像中已有依赖及项目内的测试；平台不会自动安装依赖。请检查测试是否同时覆盖正常输入与攻击输入。"}
        </p>
        <label className="stage-check" htmlFor={`rescan-${run.id}`}>
          <Checkbox
            id={`rescan-${run.id}`}
            checked={rescan}
            onCheckedChange={(checked) => setRescan(Boolean(checked))}
          />
          执行 CodeQL 复扫
        </label>
        {blocked && confirmed.length > 0 ? (
          <p className="action-hint">{blocked}</p>
        ) : null}
        <Button
          disabled={Boolean(blocked) || start.isPending}
          onClick={() => start.mutate()}
        >
          生成并验证修复 Diff
        </Button>
      </div>
      {candidates.error ? (
        <p role="alert">候选读取失败：{candidates.error.message}</p>
      ) : null}
      {start.error ? (
        <p role="alert">修复提交失败：{start.error.message}</p>
      ) : null}
      {repairs.error ? <p role="alert">{repairs.error.message}</p> : null}
      {repairs.data?.map((record) => (
        <RepairCard
          key={record.id}
          record={record}
          suiteId={suiteId}
          busy={busy}
        />
      ))}
      <StageHistory stages={stages} />
    </section>
  )
}
