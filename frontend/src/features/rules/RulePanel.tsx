import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import type { AuditRun } from "@/api/audits"
import {
  type Capabilities,
  getCandidates,
  getRuleHoldouts,
  getRules,
  type StageRun,
  startStage,
} from "@/api/stages"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { KnowledgePanel } from "@/features/knowledge/KnowledgePanel"
import { StageHistory } from "@/features/stages/StageHistory"
import { RuleCard } from "./RuleCard"
export function RulePanel({
  run,
  stages,
  capabilities,
}: {
  run: AuditRun
  stages: StageRun[]
  capabilities: Capabilities | undefined
}) {
  const [requirement, setRequirement] = useState(""),
    [strategy, setStrategy] = useState("auto"),
    [purpose, setPurpose] = useState("review_anchor"),
    [holdout, setHoldout] = useState("none"),
    [candidate, setCandidate] = useState("none")
  const [sourcePaths, setSourcePaths] = useState("")
  const cache = useQueryClient(),
    busy = stages.some((item) => ["queued", "running"].includes(item.status))
  const candidates = useQuery({
    queryKey: ["candidates", run.id],
    queryFn: () => getCandidates(run.id),
  })
  const holdouts = useQuery({
    queryKey: ["rule-holdouts"],
    queryFn: getRuleHoldouts,
  })
  const rules = useQuery({
    queryKey: ["rules", run.language],
    queryFn: () => getRules(run.language),
    refetchInterval: busy ? 3000 : false,
  })
  const start = useMutation({
    mutationFn: () =>
      startStage(run.id, "rule", {
        requirement,
        strategy,
        purpose,
        holdout_id: holdout === "none" ? null : holdout,
        candidate_id: candidate === "none" ? null : candidate,
        source_paths: sourcePaths
          .split(/\r?\n/)
          .map((path) => path.trim())
          .filter(Boolean),
      }),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <section className="stage-section">
      <h3>RAG 规则生成与验收</h3>
      <p>
        根据漏洞描述、相关源码和知识/范例生成规则，再进行编译、正反例与原项目单规则复测。样本批准、根因确认和发布分别记录。
      </p>
      <KnowledgePanel
        language={run.language}
        embeddingReady={Boolean(capabilities?.embedding_model)}
      />
      <div className="stage-form">
        <label>
          规则目标与覆盖缺口
          <textarea
            className="audit-textarea"
            value={requirement}
            onChange={(event) => setRequirement(event.target.value)}
            maxLength={5000}
          />
        </label>
        <Select
          value={purpose}
          onValueChange={(value) => {
            setPurpose(value)
            setHoldout("none")
          }}
        >
          <SelectTrigger aria-label="规则用途">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="review_anchor">
              复审锚点（不证明漏洞）
            </SelectItem>
            <SelectItem value="vulnerability_detector">漏洞检测规则</SelectItem>
            <SelectItem value="framework_model">框架建模与集成查询</SelectItem>
          </SelectContent>
        </Select>
        <Select value={holdout} onValueChange={setHoldout}>
          <SelectTrigger aria-label="独立规则测试集">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">
              未选择独立集（可生成，暂不能发布）
            </SelectItem>
            {holdouts.data
              ?.filter(
                (item) =>
                  item.language === run.language && item.purpose === purpose,
              )
              .map((item) => (
                <SelectItem key={item.id} value={item.id}>
                  {item.operation} · {item.id}
                </SelectItem>
              ))}
          </SelectContent>
        </Select>
        {holdouts.error ? <p role="alert">{holdouts.error.message}</p> : null}
        <Select value={strategy} onValueChange={setStrategy}>
          <SelectTrigger aria-label="规则生成策略">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="auto">根据覆盖分析选择</SelectItem>
            <SelectItem value="model">补充 .qll 模型</SelectItem>
            <SelectItem value="extend">扩展查询</SelectItem>
            <SelectItem value="new_query">新查询</SelectItem>
          </SelectContent>
        </Select>
        <Select value={candidate} onValueChange={setCandidate}>
          <SelectTrigger aria-label="提炼已确认缺陷">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">从明确需求生成</SelectItem>
            {candidates.data
              ?.filter((item) => item.status === "confirmed")
              .map((item) => (
                <SelectItem key={item.id} value={item.id}>
                  {item.title}
                </SelectItem>
              ))}
          </SelectContent>
        </Select>
        <label>
          相关源码路径（每行一个；选择已确认漏洞时可从关联证据自动读取）
          <textarea
            className="audit-textarea"
            value={sourcePaths}
            onChange={(event) => setSourcePaths(event.target.value)}
            maxLength={4000}
            placeholder="例如 app.py 或 services/search.py"
          />
        </label>
        <Button
          disabled={
            !capabilities?.model_configured ||
            requirement.length < 10 ||
            (candidate === "none" && !sourcePaths.trim()) ||
            busy ||
            start.isPending ||
            run.status !== "completed"
          }
          onClick={() => start.mutate()}
        >
          检索知识并生成规则
        </Button>
      </div>
      {rules.error ? <p role="alert">{rules.error.message}</p> : null}
      {rules.data
        ?.filter((item) => item.audit_id === run.id)
        .map((rule) => (
          <RuleCard
            key={rule.id}
            rule={rule}
            awaiting={stages.some(
              (item) =>
                item.id === rule.stage_id &&
                item.status === "awaiting_confirmation",
            )}
          />
        ))}
      <StageHistory stages={stages} />
    </section>
  )
}
