import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
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
import { uniqueCandidates } from "@/features/audit-task/task-summary"
import { StageHistory } from "@/features/stages/StageHistory"
import { labelPhase } from "@/features/stages/stage-labels"
import {
  type WorkflowStep,
  WorkflowSteps,
} from "@/features/stages/WorkflowSteps"
import { RepairCard } from "./RepairCard"
import { RepairTargets } from "./RepairTargets"
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
  const [selected, setSelected] = useState<string[]>([])
  const [paths, setPaths] = useState("")
  const [profile, setProfile] = useState("syntax")
  const [rescan, setRescan] = useState(true)
  const [suiteId, setSuiteId] = useState("")
  const cache = useQueryClient()
  const busy = stages.some((stage) =>
    ["queued", "running"].includes(stage.status),
  )
  const active = stages.find(
    (stage) =>
      stage.kind === "repair" && ["queued", "running"].includes(stage.status),
  )
  const repairStage = [...stages]
    .filter((stage) => stage.kind === "repair")
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))[0]
  const candidates = useQuery({
    queryKey: ["candidates", run.id],
    queryFn: () => getCandidates(run.id),
  })
  const repairs = useQuery({
    queryKey: ["repairs", run.id],
    queryFn: () => getRepairs(run.id),
    refetchInterval: busy ? 2500 : false,
  })
  const confirmed = uniqueCandidates(candidates.data ?? []).filter(
    (item) => item.status === "confirmed",
  )
  const targets = selected.filter((id) =>
    confirmed.some((item) => item.id === id),
  )
  const recordTime = (stageId: string) =>
    stages.find((stage) => stage.id === stageId)?.created_at ?? ""
  const records = [...(repairs.data ?? [])].sort((a, b) =>
    recordTime(b.stage_id).localeCompare(recordTime(a.stage_id)),
  )
  const latest = records[0]
  const comparisonStatus = latest?.comparison?.status
  const steps: WorkflowStep[] = [
    {
      title: "选择修复目标",
      detail: latest ? "修复目标已保存" : `已选 ${targets.length} 个真实漏洞`,
      status: targets.length || latest ? "done" : "active",
    },
    {
      title: "生成补丁",
      detail: active
        ? labelPhase(active.phase)
        : repairStage?.status === "failed"
          ? "本次生成失败，查看执行原因"
          : latest
            ? `${new Set(latest.changes.map((change) => change.file)).size} 个文件有修改`
            : "在隔离副本中修改源码",
      status: active
        ? "active"
        : repairStage?.status === "failed"
          ? "attention"
          : latest
            ? "done"
            : "waiting",
    },
    {
      title: "前后验证",
      detail:
        comparisonStatus === "passed"
          ? "所列用例通过"
          : comparisonStatus === "failed"
            ? "验证失败，请查看原因"
            : "对比漏洞复现与正常功能",
      status:
        comparisonStatus === "passed"
          ? "done"
          : ["failed", "inconclusive", "stale"].includes(comparisonStatus ?? "")
            ? "attention"
            : ["queued", "running"].includes(comparisonStatus ?? "")
              ? "active"
              : "waiting",
    },
    {
      title: "交付补丁",
      detail:
        latest?.status === "accepted"
          ? "已接受，可下载"
          : "审阅 Diff 与验证范围",
      status:
        latest?.status === "accepted"
          ? "done"
          : latest?.acceptance_ready
            ? "active"
            : "waiting",
    },
  ]
  const blocked = candidates.isPending
    ? "正在读取可修复漏洞…"
    : candidates.error
      ? "漏洞读取失败，请重试"
      : !confirmed.length
        ? "暂无分类为真实的漏洞"
        : !targets.length
          ? "先选择要修复的漏洞"
          : !modelReady
            ? "模型服务尚未配置"
            : busy
              ? "当前后台任务仍在执行"
              : null
  const start = useMutation({
    mutationFn: () =>
      startStage(run.id, "repair", {
        candidate_ids: targets,
        allowed_paths: paths
          .split(/\r?\n/)
          .map((item) => item.trim())
          .filter(Boolean),
        validation_profile: profile,
        rescan,
        ...(suiteId ? { verification_suite_id: suiteId } : {}),
      }),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <section className="stage-section downstream-workspace">
      <WorkflowSteps steps={steps} label="代码修复流程" />
      {candidates.isPending ? (
        <p role="status">正在读取修复目标…</p>
      ) : candidates.error ? (
        <div role="alert">
          <p>修复目标读取失败：{candidates.error.message}</p>
          <Button variant="outline" onClick={() => candidates.refetch()}>
            重新读取漏洞
          </Button>
        </div>
      ) : (
        <RepairTargets
          auditId={run.id}
          candidates={confirmed}
          selected={targets}
          busy={busy}
          onSelect={(value) => {
            setSelected(value)
            setSuiteId("")
          }}
        />
      )}
      <details className="downstream-disclosure">
        <summary>
          项目验收测试{" "}
          <span>
            {suiteId ? "已选择固定测试集" : "可稍后准备 · 未选择时生成补丁草稿"}
          </span>
        </summary>
        <VerificationSuitePanel
          auditId={run.id}
          targets={targets}
          suiteId={suiteId}
          onSelect={setSuiteId}
          modelReady={modelReady}
          busy={busy}
          stages={stages}
        />
      </details>
      <details className="downstream-disclosure">
        <summary>
          高级修复配置{" "}
          <span>
            {profile === "syntax" ? "语法检查" : "项目测试"} ·{" "}
            {rescan ? "启用 CodeQL 复扫" : "未启用复扫"}
          </span>
        </summary>
        <div className="stage-form">
          <label>
            额外允许修改的文件
            <textarea
              className="audit-textarea"
              value={paths}
              onChange={(event) => setPaths(event.target.value)}
              placeholder="关联证据文件自动加入；通常无需填写"
            />
          </label>
          <label>
            补丁验证方式
            <select
              className="native-select"
              value={profile}
              onChange={(event) => setProfile(event.target.value)}
            >
              <option value="syntax">隔离语法检查</option>
              <option
                value={
                  run.language === "python"
                    ? "python_pytest"
                    : "javascript_test"
                }
              >
                {run.language === "python"
                  ? "隔离 pytest"
                  : "隔离 Node.js 测试"}
              </option>
            </select>
          </label>
          <p className="page-note">
            语法检查不等于漏洞已修复。项目测试需运行环境已有依赖，平台不会自动安装。
          </p>
          <label className="stage-check" htmlFor={`repair-rescan-${run.id}`}>
            <Checkbox
              id={`repair-rescan-${run.id}`}
              checked={rescan}
              onCheckedChange={(checked) => setRescan(Boolean(checked))}
            />
            执行 CodeQL 复扫
          </label>
        </div>
      </details>
      <div className="downstream-submit">
        <div>
          <strong>
            {blocked ?? `为 ${targets.length} 个漏洞生成修复补丁`}
          </strong>
          <p>
            {suiteId
              ? "使用已选择的固定测试集，原始快照保留。"
              : "先生成并查看 Diff；交付前再完成项目前后验证。"}
          </p>
        </div>
        <Button
          disabled={Boolean(blocked) || start.isPending}
          onClick={() => start.mutate()}
        >
          {start.isPending ? "正在提交…" : "生成修复补丁"}
        </Button>
      </div>
      {start.error ? (
        <p role="alert">修复提交失败：{start.error.message}</p>
      ) : null}
      {repairStage?.status === "failed" ? (
        <div className="failure-notice" role="alert">
          <h4>本次修复执行失败</h4>
          <p>{repairStage.error ?? "请展开后台执行历史查看失败原因。"}</p>
          {records.length ? <p>之前已保存的补丁仍可查看。</p> : null}
        </div>
      ) : null}
      {active ? (
        <div className="downstream-progress" role="status">
          <strong>正在生成修复补丁</strong>
          <p>{labelPhase(active.phase)} · 产物保存后自动更新。</p>
        </div>
      ) : null}
      <div className="downstream-section-heading">
        <div>
          <h3>修复补丁与验证结果</h3>
          <p>先看代码改了什么，再核对检查范围和修复前后的行为。</p>
        </div>
        <span className="selection-count">{records.length} 次修复尝试</span>
      </div>
      {repairs.error ? (
        <div role="alert">
          <p>补丁读取失败：{repairs.error.message}</p>
          <Button variant="outline" onClick={() => repairs.refetch()}>
            重新读取补丁
          </Button>
        </div>
      ) : repairs.isPending ? (
        <p role="status">正在读取修复补丁…</p>
      ) : records.length ? (
        records.map((record, index) =>
          index === 0 ? (
            <RepairCard
              key={record.id}
              record={record}
              suiteId={suiteId}
              busy={busy}
            />
          ) : (
            <details className="downstream-disclosure" key={record.id}>
              <summary>历史修复尝试 · {record.id.slice(0, 8)}</summary>
              <RepairCard record={record} suiteId={suiteId} busy={busy} />
            </details>
          ),
        )
      ) : (
        <div className="downstream-empty">
          <h4>尚未生成补丁</h4>
          <p>
            选择漏洞后开始修复。生成后将在此展示文件列表、真实代码 Diff
            与验证结果。
          </p>
        </div>
      )}
      <details className="downstream-disclosure">
        <summary>后台执行历史</summary>
        <StageHistory stages={stages} />
      </details>
    </section>
  )
}
