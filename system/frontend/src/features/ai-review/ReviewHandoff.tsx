import { z } from "zod"
import { Button } from "@/components/ui/button"

const handoff = z.object({
  candidate_id: z.string(),
  location: z.object({ file: z.string(), line: z.number() }),
  state: z.enum(["assessed", "unresolved", "unreviewed"]),
  reason_code: z.string().nullable(),
  reason: z.string().nullable(),
  checked_premises: z.array(z.string()),
  missing_premises: z.array(z.string()),
  missing_checks: z.array(z.object({ reason: z.string() })),
  runtime_unknowns: z.array(z.string()),
  rejected_reasons: z.array(z.string()),
})

const reasons: Record<string, string> = {
  insufficient_evidence: "证据不足",
  pending_assessment: "尚无明确建议",
  assessment_rejected: "复核结果未通过校验",
  assessment_omitted: "本轮没有返回该候选的结果",
  outside_batch_limit: "本轮批次上限未覆盖",
  not_attempted: "本轮尚未处理",
  budget_exhausted: "模型预算耗尽",
  unit_budget: "批次步数耗尽",
  context_budget: "上下文超过预算",
  timeout: "模型调用超时",
  rate_limited: "模型接口限流",
  provider_error: "模型接口调用失败",
  no_progress: "复核停止推进",
  verification_failed: "复核执行失败",
}

export function ReviewHandoff({
  records,
  disabled,
  onContinue,
}: {
  records: unknown
  disabled?: boolean
  onContinue?: (id: string) => void
}) {
  // Peer: research discovery/review_handoff.py via the projected discovery trace.
  // Older stages have no handoff field.
  const parsed = z.array(handoff).safeParse(records)
  if (!parsed.success) return null

  const unresolved = parsed.data.filter((row) => row.state !== "assessed")
  if (!unresolved.length) return null

  return (
    <details className="review-footer-disclosure">
      <summary>未决候选复核记录（{unresolved.length}）</summary>
      <ul>
        {unresolved.map((row) => {
          const notes = [
            ["已核查", row.checked_premises],
            [
              "待补证",
              [
                ...new Set([
                  ...row.missing_premises,
                  ...row.missing_checks.map((check) => check.reason),
                ]),
              ],
            ],
            ["需确认的运行条件", row.runtime_unknowns],
            ["校验反馈", row.rejected_reasons],
          ] as const
          const code = row.reason_code ?? ""
          return (
            <li key={row.candidate_id}>
              <strong>
                {row.location.file}:{row.location.line} ·{" "}
                {reasons[code] ?? code}
              </strong>
              {onContinue ? (
                <Button
                  type="button"
                  variant="outline"
                  disabled={disabled}
                  onClick={() => onContinue(row.candidate_id)}
                >
                  继续复审此候选
                </Button>
              ) : null}
              {row.reason ? <p>{row.reason}</p> : null}
              {notes.map(([label, values]) =>
                values.length ? (
                  <p key={label}>
                    {label}：{values.join("；")}
                  </p>
                ) : null,
              )}
            </li>
          )
        })}
      </ul>
    </details>
  )
}
