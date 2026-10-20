import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { getRuleDrafts, type StageRun } from "@/api/stages"
import { WorkspaceSelect } from "@/components/WorkspaceSelect"
import { RuleCodeView } from "./RuleCodeView"

export function RuleDraftPreview({ stage }: { stage: StageRun }) {
  const [attempt, setAttempt] = useState("")
  const drafts = useQuery({
    queryKey: ["rule-drafts", stage.id],
    queryFn: () => getRuleDrafts(stage.id),
  })
  const draft =
    drafts.data?.find((row) => String(row.attempt) === attempt) ??
    drafts.data?.[0]
  if (drafts.isPending) return <p role="status">正在读取本次规则草稿…</p>
  if (drafts.error)
    return <p role="alert">草稿读取失败：{drafts.error.message}</p>
  if (!draft)
    return (
      <p className="page-note">
        本次执行尚未生成查询代码。上方显示具体失败原因，历史规则版本仍保留。
      </p>
    )
  return (
    <section
      className="rule-draft-preview"
      aria-label="本次未通过验收的规则草稿"
    >
      <h4>本次生成草稿 · 尚未通过验收</h4>
      <p>可查看与复制生成文本；此草稿不可发布，也不会用于新扫描。</p>
      {(drafts.data?.length ?? 0) > 1 && (
        <WorkspaceSelect
          aria-label="查看生成尝试"
          value={String(draft.attempt)}
          onValueChange={setAttempt}
          options={drafts.data!.map((row) => ({
            value: String(row.attempt),
            label: `第 ${row.attempt} 次生成`,
          }))}
        />
      )}
      {draft.diagnostic && <p role="alert">{draft.diagnostic.message}</p>}
      <RuleCodeView
        key={draft.attempt}
        query={draft.query}
        modules={draft.modules}
      />
    </section>
  )
}
