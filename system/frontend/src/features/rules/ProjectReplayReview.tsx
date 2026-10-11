import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { confirmProjectMatch, type RuleVersion } from "@/api/stages"
import { Button } from "@/components/ui/button"

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
  return (
    <section className="stage-form">
      <h4>原项目单规则复测：{replay.status}</h4>
      <p>
        请核对输入源、传播、防护与汇点是否对应同一已确认漏洞。位置或 CWE
        相近只提供匹配线索；其他告警仍待审查。
      </p>
      {[
        "candidate_match_needs_confirmation",
        "baseline_match_needs_confirmation",
      ].includes(replay.status) ? (
        <>
          <label>
            对应目标根因的结果
            <select
              value={finding}
              onChange={(event) => setFinding(event.target.value)}
            >
              <option value="">请选择并核对路径</option>
              {replay.findings
                .filter((item) => replay.matched_ids.includes(item.id))
                .map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.locations[0]?.file}:{item.locations[0]?.line} ·{" "}
                    {item.message}
                  </option>
                ))}
            </select>
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
          {replay.baseline_matching_ids?.length ? (
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
              (replay.baseline_matching_ids?.length > 0 &&
                baselineReason.trim().length < 10) ||
              confirm.isPending
            }
            onClick={() => confirm.mutate()}
          >
            确认新规则补上此漏洞
          </Button>
        </>
      ) : null}
    </section>
  )
}
