import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import type { AuditRun } from "@/api/audits"
import {
  type Capabilities,
  getCandidates,
  getRuleHoldouts,
  startStage,
} from "@/api/stages"
import { Button } from "@/components/ui/button"
import { uniqueCandidates } from "@/features/audit-task/task-summary"

export function RuleGenerationForm({
  run,
  capabilities,
  busy,
}: {
  run: AuditRun
  capabilities: Capabilities | undefined
  busy: boolean
}) {
  const [requirement, setRequirement] = useState("")
  const [candidateId, setCandidateId] = useState("none")
  const [purpose, setPurpose] = useState("vulnerability_detector")
  const [strategy, setStrategy] = useState("auto")
  const [holdout, setHoldout] = useState("none")
  const [paths, setPaths] = useState("")
  const cache = useQueryClient()
  const candidates = useQuery({
    queryKey: ["candidates", run.id],
    queryFn: () => getCandidates(run.id),
    retry: false,
  })
  const holdouts = useQuery({
    queryKey: ["rule-holdouts"],
    queryFn: getRuleHoldouts,
  })
  const confirmed = uniqueCandidates(candidates.data ?? []).filter(
    (item) => item.status === "confirmed",
  )
  const selected = confirmed.find((item) => item.id === candidateId)
  const selectedHoldout = holdouts.data?.find(
    (item) =>
      item.id === holdout &&
      item.language === run.language &&
      item.purpose === purpose,
  )
  const effectiveRequirement =
    requirement.trim() ||
    (selected
      ? `检测与「${selected.review?.detail?.title ?? selected.title}」相同的漏洞条件，依据原始源码和复核证据提炼规则，避免匹配正常行为。`
      : "")
  const blocked = candidates.isPending
    ? "正在读取漏洞…"
    : candidates.error
      ? "漏洞读取失败，请重新读取"
      : !capabilities?.model_configured
        ? "模型服务尚未配置"
        : !selected && !paths.trim()
          ? "选择真实漏洞，或填写明确的源码范围"
          : effectiveRequirement.length < 10
            ? "补充至少 10 个字符的规则目标"
            : busy
              ? "当前规则任务仍在执行"
              : run.status !== "completed"
                ? "等待审计发现完成"
                : null
  const start = useMutation({
    mutationFn: () =>
      startStage(run.id, "rule", {
        requirement: effectiveRequirement,
        purpose,
        strategy,
        candidate_id: selected?.id ?? null,
        holdout_id: selectedHoldout?.id ?? null,
        source_paths: paths
          .split(/\r?\n/)
          .map((path) => path.trim())
          .filter(Boolean),
      }),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <div className="rule-generation downstream-rule-form">
      <section className="form-section">
        <div className="downstream-section-heading">
          <div>
            <h3>选择要提炼的漏洞</h3>
            <p>默认生成漏洞检测规则，平台自动选择检索和生成策略。</p>
          </div>
        </div>
        <div className="stage-form">
          <label>
            规则来源
            <select
              className="native-select"
              aria-label="规则来源"
              value={selected?.id ?? "none"}
              onChange={(event) => setCandidateId(event.target.value)}
            >
              <option value="none">选择真实漏洞，或从明确需求生成</option>
              {confirmed.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.review?.detail?.title ?? item.title} ·{" "}
                  {item.location.file}:{item.location.line}
                </option>
              ))}
            </select>
          </label>
          {selected ? (
            <div className="rule-selected-target">
              <strong>
                {selected.review?.detail?.title ?? selected.title}
              </strong>
              <p>
                {selected.location.file}:{selected.location.line} ·{" "}
                {selected.weakness}
              </p>
              <small>从关联证据提炼，通常无需另填源码路径。</small>
            </div>
          ) : (
            <label>
              源码范围（从需求生成时必填）
              <textarea
                className="audit-textarea"
                value={paths}
                onChange={(event) => setPaths(event.target.value)}
                placeholder="快照内文件或目录，例如 app.py"
              />
            </label>
          )}
          <label>
            补充规则目标{selected ? "（可选）" : ""}
            <textarea
              className="audit-textarea"
              value={requirement}
              onChange={(event) => setRequirement(event.target.value)}
              maxLength={5000}
              placeholder={
                selected
                  ? "留空按所选漏洞的实际条件生成；可补充需要覆盖或排除的场景"
                  : "说明需要检测的漏洞条件与正常行为边界"
              }
            />
          </label>
          {candidates.error ? (
            <p role="alert">{candidates.error.message}</p>
          ) : null}
        </div>
      </section>
      <details className="downstream-disclosure">
        <summary>
          独立验收测试集{" "}
          <span>
            {selectedHoldout ? "已选择" : "可生成草稿 · 未选择时不能发布"}
          </span>
        </summary>
        <div className="stage-form">
          <label>
            独立规则测试集
            <select
              className="native-select"
              aria-label="独立规则测试集"
              value={selectedHoldout?.id ?? "none"}
              onChange={(event) => setHoldout(event.target.value)}
            >
              <option value="none">暂不选择，仅生成与检查草稿</option>
              {holdouts.data
                ?.filter(
                  (item) =>
                    item.language === run.language && item.purpose === purpose,
                )
                .map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.operation} · {item.id}
                  </option>
                ))}
            </select>
          </label>
          <p className="page-note">
            独立测试与开发正反例分别验收，全部发布门满足后才可发布。
          </p>
          {holdouts.error ? (
            <p role="alert">测试集读取失败：{holdouts.error.message}</p>
          ) : null}
        </div>
      </details>
      <details className="downstream-disclosure">
        <summary>
          高级规则设置{" "}
          <span>
            {purpose === "vulnerability_detector"
              ? "漏洞检测规则"
              : purpose === "review_anchor"
                ? "复审锚点"
                : "框架建模"}{" "}
            · 自动检索
          </span>
        </summary>
        <div className="stage-form">
          <label>
            规则用途
            <select
              className="native-select"
              aria-label="规则用途"
              value={purpose}
              onChange={(event) => {
                setPurpose(event.target.value)
                setHoldout("none")
              }}
            >
              <option value="vulnerability_detector">漏洞检测规则</option>
              <option value="review_anchor">复审锚点（不证明漏洞）</option>
              <option value="framework_model">框架建模与集成查询</option>
            </select>
          </label>
          <label>
            生成策略
            <select
              className="native-select"
              value={strategy}
              onChange={(event) => setStrategy(event.target.value)}
            >
              <option value="auto">自动选择</option>
              <option value="model">补充模型</option>
              <option value="extend">扩展查询</option>
              <option value="new_query">新建查询</option>
            </select>
          </label>
          {selected ? (
            <label>
              额外源码路径
              <textarea
                className="audit-textarea"
                value={paths}
                onChange={(event) => setPaths(event.target.value)}
              />
            </label>
          ) : null}
          <p className="page-note">
            检索匹配语言及 CodeQL 库版本的参考资料与完整范例。技术方式：
            {capabilities?.retrieval ?? "读取中"}
          </p>
        </div>
      </details>
      <div className="downstream-submit">
        <div>
          <strong>{blocked ?? "目标已准备好"}</strong>
          <p>生成后查看查询、正反例与项目命中；不会自动发布。</p>
          {start.error ? (
            <p role="alert">提交失败：{start.error.message}</p>
          ) : null}
        </div>
        <Button
          disabled={Boolean(blocked) || start.isPending}
          onClick={() => start.mutate()}
        >
          {start.isPending ? "正在提交…" : "生成检测规则"}
        </Button>
      </div>
    </div>
  )
}
