import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import type { AuditRun } from "@/api/audits"
import {
  type Capabilities,
  getCandidates,
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
    [candidate, setCandidate] = useState("none")
  const cache = useQueryClient(),
    busy = stages.some((item) => ["queued", "running"].includes(item.status))
  const candidates = useQuery({
    queryKey: ["candidates", run.id],
    queryFn: () => getCandidates(run.id),
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
        candidate_id: candidate === "none" ? null : candidate,
      }),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <section className="stage-section">
      <h3>RAG 规则生成与验收</h3>
      <p>
        先检索知识与分析已有覆盖，再选择建模、扩展或新查询。样本批准、验收和发布分别记录。
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
        <Button
          disabled={
            !capabilities?.model_configured ||
            requirement.length < 10 ||
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
