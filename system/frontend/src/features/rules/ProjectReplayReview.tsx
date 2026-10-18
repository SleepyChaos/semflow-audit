import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useId, useState } from "react"
import { toast } from "sonner"
import { confirmProjectMatch, type RuleVersion } from "@/api/stages"
import { Button } from "@/components/ui/button"
import { WorkspaceSelect } from "@/components/WorkspaceSelect"

interface Replay {
  status: string
  matched_ids: string[]
  baseline_matching_ids: string[]
  findings: {
    id: string
    message: string
    locations: { file: string; line: number }[]
    code_flows: unknown[]
  }[]
}

export function ProjectReplayReview({ rule }: { rule: RuleVersion }) {
  const selectionId = useId()
  const replay = rule.validation.project_replay as Replay | undefined
  const [finding, setFinding] = useState("")
  const [reason, setReason] = useState("")
  const [baselineReason, setBaselineReason] = useState("")
  const cache = useQueryClient()
  const confirm = useMutation({
    mutationFn: () =>
      confirmProjectMatch(
        rule.id,
        finding,
        reason,
        baselineReason || undefined,
      ),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["rules"] }),
    onError: (error: Error) => toast.error(error.message),
  })
  if (!replay) return null
  const baselineReuse = replay.status === "already_covered"
  return (
    <section className="stage-form">
      <h4>
        原项目单规则复测：
        {baselineReuse ? "命中目标，原基线已覆盖" : replay.status}
      </h4>
      {baselineReuse ? (
        <p>
          规则已命中此漏洞，可继续验证并复用；这属于基线能力复用，不计为新增检出。
        </p>
      ) : null}
      <p>
        请核对输入源、传播、防护与汇点是否对应同一已确认漏洞。位置或 CWE
        相近只提供匹配线索；其他告警仍待审查。
      </p>
      {[
        "candidate_match_needs_confirmation",
        "baseline_match_needs_confirmation",
        "already_covered",
      ].includes(replay.status) ? (
        <>
          <label htmlFor={selectionId}>
            对应目标根因的结果
            <WorkspaceSelect
              id={selectionId}
              value={finding}
              onValueChange={setFinding}
              options={[
                { value: "", label: "请选择并核对路径" },
                ...replay.findings
                  .filter((item) => replay.matched_ids.includes(item.id))
                  .map((item) => ({
                    value: item.id,
                    label: (
                      <>
                        {item.locations[0]?.file}:{item.locations[0]?.line} ·{" "}
                        {item.message}
                      </>
                    ),
                  })),
              ]}
            />
          </label>
          {finding ? (
            <pre className="source-code">
              {JSON.stringify(
                replay.findings.find((item) => item.id === finding),
                null,
                2,
              )}
            </pre>
          ) : null}
          <label>
            根因与路径确认依据
            <textarea
              className="audit-textarea"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              maxLength={4000}
            />
          </label>
          {!baselineReuse && replay.baseline_matching_ids?.length ? (
            <label>
              原基线相近结果不属于此目标的依据
              <textarea
                className="audit-textarea"
                value={baselineReason}
                onChange={(event) => setBaselineReason(event.target.value)}
                maxLength={4000}
              />
            </label>
          ) : null}
          <Button
            disabled={
              !finding ||
              reason.trim().length < 10 ||
              (!baselineReuse &&
                replay.baseline_matching_ids?.length > 0 &&
                baselineReason.trim().length < 10) ||
              confirm.isPending
            }
            onClick={() => confirm.mutate()}
          >
            {baselineReuse ? "确认规则复用与目标路径" : "确认规则命中目标根因"}
          </Button>
        </>
      ) : null}
    </section>
  )
}
