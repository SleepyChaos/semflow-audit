// biome-ignore-all lint/a11y/noNoninteractiveTabindex: 代码对比滚动区域需要键盘焦点，以便方向键和 PageDown 阅读。
import { useQuery } from "@tanstack/react-query"
import { FileCode2, GitCompareArrows } from "lucide-react"
import { useState } from "react"
import { apiFetch } from "@/api/backend"
import type { RepairRecord } from "@/api/stages"
import { Button } from "@/components/ui/button"
import { useIsMobile } from "@/hooks/useMobile"
import { type DiffLine, type DiffRow, parseRepairDiff } from "./diff-model"

function Cell({ line, side }: { line?: DiffLine; side: "before" | "after" }) {
  return (
    <td
      className={`diff-cell ${line?.changed ? (side === "before" ? "diff-removed" : "diff-added") : ""}`}
    >
      <span
        className="diff-line-number"
        title={
          line
            ? `${side === "before" ? "原始" : "修复后"}代码第 ${line.number} 行`
            : undefined
        }
      >
        {line?.number ?? ""}
      </span>
      <span className="diff-marker" aria-hidden="true">
        {line?.changed ? (side === "before" ? "−" : "+") : " "}
      </span>
      <code>{line?.text ?? ""}</code>
    </td>
  )
}
function Rows({ rows, mode }: { rows: DiffRow[]; mode: string }) {
  return (
    <tbody>
      {rows.map((row, index) =>
        row.section || row.note ? (
          <tr className="diff-section" key={index}>
            <td colSpan={mode === "split" ? 2 : 1}>
              {row.section ?? row.note}
            </td>
          </tr>
        ) : mode === "split" ? (
          <tr key={index}>
            <Cell line={row.before} side="before" />
            <Cell line={row.after} side="after" />
          </tr>
        ) : row.before?.changed || row.after?.changed ? (
          <RowsChanged key={index} row={row} />
        ) : (
          <tr key={index}>
            <Cell line={row.after ?? row.before} side="after" />
          </tr>
        ),
      )}
    </tbody>
  )
}
function RowsChanged({ row }: { row: DiffRow }) {
  return (
    <>
      {row.before ? (
        <tr>
          <Cell line={row.before} side="before" />
        </tr>
      ) : null}
      {row.after ? (
        <tr>
          <Cell line={row.after} side="after" />
        </tr>
      ) : null}
    </>
  )
}
export function RepairDiff({ record }: { record: RepairRecord }) {
  const mobile = useIsMobile()
  const [chosenMode, setMode] = useState<string | null>(null)
  const mode = chosenMode ?? (mobile ? "unified" : "split")
  const [selected, setSelected] = useState("")
  const diff = useQuery({
    queryKey: ["repair-diff", record.id],
    queryFn: async () =>
      parseRepairDiff(
        await (await apiFetch(`/repairs/${record.id}/diff`)).text(),
      ),
    staleTime: Infinity,
    retry: false,
  })
  const files = diff.data ?? []
  const file = files.find((item) => item.name === selected) ?? files[0]
  const reasons = record.changes.filter((change) => change.file === file?.name)
  return (
    <section className="repair-diff" aria-label="修复前后代码 Diff">
      <div className="downstream-section-heading">
        <div>
          <h4>
            <GitCompareArrows size={18} />
            修复前后代码 Diff
          </h4>
          <p>
            真实补丁与源码行号 · 红色删除，绿色新增；显示修改区域及其上下文。
          </p>
        </div>
        <fieldset className="diff-view-controls" aria-label="Diff 显示方式">
          <Button
            size="sm"
            variant={mode === "split" ? "default" : "outline"}
            aria-pressed={mode === "split"}
            onClick={() => setMode("split")}
          >
            并排对比
          </Button>
          <Button
            size="sm"
            variant={mode === "unified" ? "default" : "outline"}
            aria-pressed={mode === "unified"}
            onClick={() => setMode("unified")}
          >
            逐行对比
          </Button>
        </fieldset>
      </div>
      {diff.isPending ? (
        <p role="status">正在读取真实补丁…</p>
      ) : diff.error ? (
        <div role="alert">
          <p>代码对比读取失败：{diff.error.message}</p>
          <Button size="sm" variant="outline" onClick={() => diff.refetch()}>
            重新读取 Diff
          </Button>
        </div>
      ) : (
        <>
          <fieldset className="diff-file-tabs" aria-label="修改文件">
            {files.map((item) => (
              <Button
                key={item.name}
                size="sm"
                variant={file?.name === item.name ? "secondary" : "ghost"}
                aria-pressed={file?.name === item.name}
                onClick={() => setSelected(item.name)}
              >
                <FileCode2 size={15} />
                {item.name}
                <span className="diff-add-count">+{item.added}</span>
                <span className="diff-remove-count">−{item.removed}</span>
              </Button>
            ))}
          </fieldset>
          {file ? (
            <>
              <div className="diff-reasons">
                {reasons.map((change, index) => (
                  <p key={index}>{change.reason}</p>
                ))}
              </div>
              <section
                className="diff-scroll"
                tabIndex={0}
                aria-label={`${file.name} 代码对比`}
              >
                <table className={`diff-table diff-${mode}`}>
                  <caption className="sr-only">
                    {file.name} 修复前后代码对比
                  </caption>
                  <thead>
                    <tr>
                      {mode === "split" ? (
                        <>
                          <th>修复前 · 原始代码</th>
                          <th>修复后 · 补丁代码</th>
                        </>
                      ) : (
                        <th>删除（−）与新增（+）代码</th>
                      )}
                    </tr>
                  </thead>
                  <Rows rows={file.rows} mode={mode} />
                </table>
              </section>
            </>
          ) : (
            <p>该补丁没有可展示的修改片段，请核对原始 Diff。</p>
          )}
        </>
      )}
    </section>
  )
}
