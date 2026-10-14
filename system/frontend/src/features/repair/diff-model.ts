import { parsePatch } from "diff"

export interface DiffLine {
  number: number
  text: string
  changed: boolean
}
export interface DiffRow {
  before?: DiffLine
  after?: DiffLine
  section?: string
  note?: string
}
export interface DiffFile {
  name: string
  rows: DiffRow[]
  added: number
  removed: number
}

export function parseRepairDiff(text: string): DiffFile[] {
  if (!text.trim()) throw new Error("补丁内容为空，无法展示代码对比。")
  const patches = parsePatch(text)
  if (
    !patches.length ||
    patches.some(
      (patch) =>
        !patch.hunks.length || !patch.oldFileName || !patch.newFileName,
    )
  )
    throw new Error("补丁格式无法识别，请下载原始 Diff 核对。")
  return patches.map((patch) => {
    const rows: DiffRow[] = []
    let added = 0,
      removed = 0
    for (const hunk of patch.hunks) {
      rows.push({
        section: `@@ -${hunk.oldStart},${hunk.oldLines} +${hunk.newStart},${hunk.newLines} @@`,
      })
      let oldNumber = hunk.oldStart,
        newNumber = hunk.newStart
      let before: DiffLine[] = [],
        after: DiffLine[] = []
      const flush = () => {
        for (
          let index = 0;
          index < Math.max(before.length, after.length);
          index++
        )
          rows.push({ before: before[index], after: after[index] })
        before = []
        after = []
      }
      for (const line of hunk.lines) {
        const prefix = line[0],
          content = line.slice(1)
        if (prefix === "-") {
          before.push({ number: oldNumber++, text: content, changed: true })
          removed++
        } else if (prefix === "+") {
          after.push({ number: newNumber++, text: content, changed: true })
          added++
        } else {
          flush()
          if (prefix === " ")
            rows.push({
              before: { number: oldNumber++, text: content, changed: false },
              after: { number: newNumber++, text: content, changed: false },
            })
          else if (prefix === "\\")
            rows.push({ note: "该位置的文件末尾没有换行符" })
        }
      }
      flush()
    }
    return {
      name: (patch.newFileName === "/dev/null"
        ? patch.oldFileName!
        : patch.newFileName!
      ).replace(/^[ab]\//, ""),
      rows,
      added,
      removed,
    }
  })
}
