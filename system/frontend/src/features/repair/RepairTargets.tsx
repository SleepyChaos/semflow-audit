import { useId } from "react"
import type { Candidate, RepairRecord, StageRun } from "@/api/stages"
import { Checkbox } from "@/components/ui/checkbox"
import {
  candidateMemberIds,
  candidateSourceLabel,
} from "@/features/ai-review/review-status"
import { repairProgressState } from "./repair-progress"

export function RepairTargets({
  candidates,
  selected,
  focused,
  onSelect,
  onFocus,
  busy,
  records,
  stages,
}: {
  candidates: Candidate[]
  selected: string[]
  focused?: string
  onSelect: (value: string[]) => void
  onFocus: (id: string) => void
  busy: boolean
  records: RepairRecord[]
  stages: StageRun[]
}) {
  const selectAllId = useId()
  return (
    <aside className="candidate-rail result-rail" aria-label="修复漏洞列表">
      <div className="rail-heading">
        <label className="repair-select-all" htmlFor={selectAllId}>
          <Checkbox
            id={selectAllId}
            aria-label="全选漏洞"
            checked={
              selected.length === candidates.length && candidates.length > 0
                ? true
                : selected.length > 0
                  ? "indeterminate"
                  : false
            }
            disabled={busy || !candidates.length}
            onCheckedChange={(checked) =>
              onSelect(
                checked === true ? candidates.map((item) => item.id) : [],
              )
            }
          />
          全选漏洞
        </label>
        <span>
          已选 {selected.length} / {candidates.length}
        </span>
      </div>
      <div className="result-list">
        {candidates.map((item) => {
          const members = candidateMemberIds(item)
          const attempts = records.filter((row) =>
            members.some((id) => row.candidate_ids.includes(id)),
          )
          const progress = repairProgressState(stages, records, members)
          return (
            <div
              className="repair-target-row"
              data-active={focused === item.id}
              key={item.id}
            >
              <Checkbox
                aria-label={`选择修复：${item.review?.detail?.title ?? item.title}`}
                checked={selected.includes(item.id)}
                disabled={busy}
                onCheckedChange={(checked) =>
                  onSelect(
                    checked
                      ? [...selected, item.id]
                      : selected.filter((id) => id !== item.id),
                  )
                }
              />
              <button
                type="button"
                className="candidate-option"
                aria-pressed={focused === item.id}
                onClick={() => onFocus(item.id)}
              >
                <span>{item.review?.detail?.title ?? item.title}</span>
                <small>{candidateSourceLabel(item)}</small>
                <small>
                  {item.location.file ?? "位置待核实"}:
                  {item.location.line ?? "—"} · {item.weakness}
                </small>
                <RepairProgressBadges progress={progress} />
                <small>
                  {attempts.length
                    ? `${attempts.length} 次修复尝试`
                    : "尚未生成补丁"}
                </small>
              </button>
            </div>
          )
        })}
        {!candidates.length && (
          <p className="page-note">
            暂无确认真实的漏洞，请先在 AI 复审中核对分类。
          </p>
        )}
      </div>
    </aside>
  )
}

export function RepairProgressBadges({
  progress,
}: {
  progress: ReturnType<typeof repairProgressState>
}) {
  const { current, steps } = progress
  return (
    <span className="repair-progress-labels">
      {steps.slice(0, 3).map((step) => (
        <span
          key={step.title}
          className="repair-progress-badge"
          data-status={step.status}
          title={step.detail}
        >
          {step.status === "done"
            ? "✓ "
            : step.status === "attention"
              ? "⚠ "
              : ""}
          {step.title} ·{" "}
          {step.status === "attention"
            ? "受阻"
            : step.status === "done"
              ? "已完成"
              : step.status === "active"
                ? "待完成"
                : "待开始"}
        </span>
      ))}
      {current.status === "attention" && (
        <small className="repair-block-reason">{current.detail}</small>
      )}
    </span>
  )
}
