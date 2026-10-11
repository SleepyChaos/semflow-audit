import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
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
  const [requirement, setRequirement] = useState(""),
    [strategy, setStrategy] = useState("auto"),
    [purpose, setPurpose] = useState("review_anchor"),
    [holdout, setHoldout] = useState("none"),
    [candidate, setCandidate] = useState("none"),
    [sourcePaths, setSourcePaths] = useState("")
  const cache = useQueryClient(),
    candidates = useQuery({
      queryKey: ["candidates", run.id],
      queryFn: () => getCandidates(run.id),
      retry: false,
    }),
    holdouts = useQuery({
      queryKey: ["rule-holdouts"],
      queryFn: getRuleHoldouts,
    })
  const confirmed = uniqueCandidates(candidates.data ?? []).filter(
    (c) => c.status === "confirmed",
  )
  const selectedCandidate = confirmed.some((c) => c.id === candidate)
    ? candidate
    : "none"
  const selectedHoldout = holdouts.data?.find(
    (h) =>
      h.id === holdout && h.language === run.language && h.purpose === purpose,
  )
  const start = useMutation({
    mutationFn: () =>
      startStage(run.id, "rule", {
        requirement,
        strategy,
        purpose,
        holdout_id: selectedHoldout?.id ?? null,
        candidate_id: selectedCandidate === "none" ? null : selectedCandidate,
        source_paths: sourcePaths
          .split(/\r?\n/)
          .map((p) => p.trim())
          .filter(Boolean),
      }),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  const blocked = !capabilities?.model_configured
    ? "模型服务尚未配置"
    : requirement.trim().length < 10
      ? "请填写至少 10 个字符的规则目标"
      : selectedCandidate === "none" && !sourcePaths.trim()
        ? "请填写快照中的源码路径，或选择已确认缺陷"
        : busy
          ? "当前阶段正在执行，请等待或取消"
          : run.status !== "completed"
            ? "等待扫描完成后生成规则"
            : null
  return (
    <div className="rule-generation">
      <section className="form-section">
        <div className="section-heading">
          <h3>01 / 规则目标</h3>
          <span className="page-note">定义需要补充的覆盖</span>
        </div>
        <div className="stage-form">
          <label>
            规则目标与覆盖缺口
            <textarea
              className="audit-textarea"
              value={requirement}
              onChange={(e) => setRequirement(e.target.value)}
              maxLength={5000}
              placeholder="例如：补充识别 Flask GET 装饰器路由中，将请求参数未经转义返回 HTML 的反射型 XSS。"
            />
          </label>
          <div className="form-columns">
            <label>
              规则用途
              <select
                aria-label="规则用途"
                className="native-select"
                value={purpose}
                onChange={(e) => {
                  setPurpose(e.target.value)
                  setHoldout("none")
                }}
              >
                <option value="review_anchor">复审锚点（不证明漏洞）</option>
                <option value="vulnerability_detector">漏洞检测规则</option>
                <option value="framework_model">框架建模与集成查询</option>
              </select>
            </label>
            <label>
              提炼已确认缺陷
              <select
                className="native-select"
                aria-label="提炼已确认缺陷"
                value={selectedCandidate}
                onChange={(e) => setCandidate(e.target.value)}
              >
                <option value="none">从明确需求生成</option>
                {confirmed.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label>
            相关源码路径（每行一个）
            <textarea
              className="audit-textarea"
              value={sourcePaths}
              onChange={(e) => setSourcePaths(e.target.value)}
              maxLength={4000}
              placeholder="app.py"
            />
          </label>
          <p className="page-note">
            选择已确认缺陷后，可从关联证据读取源码；仅生成锚点不能证明漏洞。
          </p>
          {candidates.error && (
            <p role="alert">候选读取失败：{candidates.error.message}</p>
          )}
        </div>
      </section>
      <section className="form-section">
        <h3>02 / 检索与生成策略</h3>
        <div className="stage-form">
          <p className="page-note">
            材料须匹配 {run.language === "python" ? "Python" : "JavaScript"}{" "}
            和固定 CodeQL 语言库版本。
            {run.language === "python"
              ? "当前 python-all 4.0.10。"
              : "当前 javascript-all 2.4.0。"}
            正文内容哈希与语言库版本是不同字段，由服务端检查匹配。
          </p>
          <Link
            className="text-action"
            to="/knowledge"
            search={{ auditId: run.id }}
          >
            检查知识库与版本 →
          </Link>
          <label>
            规则生成策略
            <select
              className="native-select"
              aria-label="规则生成策略"
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
            >
              <option value="auto">根据覆盖分析选择</option>
              <option value="model">补充 .qll 模型</option>
              <option value="extend">扩展查询</option>
              <option value="new_query">新查询</option>
            </select>
          </label>
          <p className="page-note">
            检索方式：{capabilities?.retrieval ?? "读取中"}
            。生成会引用实际匹配的知识与范例。
          </p>
        </div>
      </section>
      <section className="form-section">
        <h3>03 / 独立验收</h3>
        <div className="stage-form">
          <label>
            独立规则测试集
            <select
              aria-label="独立规则测试集"
              className="native-select"
              value={selectedHoldout?.id ?? "none"}
              onChange={(e) => setHoldout(e.target.value)}
            >
              <option value="none">未选择独立集（可生成，暂不能发布）</option>
              {holdouts.data
                ?.filter(
                  (h) => h.language === run.language && h.purpose === purpose,
                )
                .map((h) => (
                  <option value={h.id} key={h.id}>
                    {h.operation} · {h.id}
                  </option>
                ))}
            </select>
          </label>
          {holdouts.error && <p role="alert">{holdouts.error.message}</p>}
          <p className="page-note">
            编译和自生成样本通过后，仍需独立测试、人工批准样本、核对项目根因，再发布版本。
          </p>
        </div>
      </section>
      <div className="form-submit">
        <div>
          {blocked ? (
            <p className="action-hint">{blocked}</p>
          ) : (
            <p className="page-note">
              生成后请核对规则、样本与项目命中，不会自动发布。
            </p>
          )}
          {start.error && (
            <p role="alert">生成提交失败：{start.error.message}</p>
          )}
        </div>
        <Button
          disabled={Boolean(blocked) || start.isPending}
          onClick={() => start.mutate()}
        >
          {start.isPending ? "正在提交…" : "检索知识并生成规则"}
        </Button>
      </div>
    </div>
  )
}
