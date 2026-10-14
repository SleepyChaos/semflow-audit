import assert from "node:assert/strict"
import test from "node:test"
import { createTwoFilesPatch } from "diff"
import { parseRepairDiff } from "../src/features/repair/diff-model.ts"

test("真实补丁保留文件边界、源码行号和新增删除计数", () => {
  const source =
    "from flask import request\n\ndef view():\n    return request.args['payload']\n"
  const patched =
    "from flask import request\nfrom markupsafe import escape\n\ndef view():\n    return str(escape(request.args['payload']))\n"
  const first = createTwoFilesPatch("a/app.py", "b/app.py", source, patched)
  const second = createTwoFilesPatch(
    "a/config.py",
    "b/config.py",
    "DEBUG = True\n",
    "DEBUG = False\n",
  )
  const files = parseRepairDiff(first + second)
  assert.deepEqual(
    files.map((file) => file.name),
    ["app.py", "config.py"],
  )
  assert.equal(files[0].added, 2)
  assert.equal(files[0].removed, 1)
  const removed = files[0].rows.flatMap((row) =>
    row.before?.changed ? [row.before] : [],
  )
  const added = files[0].rows.flatMap((row) =>
    row.after?.changed ? [row.after] : [],
  )
  assert.equal(removed[0].number, 4)
  assert.equal(added[1].number, 5)
  assert.equal(
    files[1].rows.find((row) => row.before)?.before.text,
    "DEBUG = True",
  )
})
test("无末尾换行的补丁显示限制，空内容和无效补丁不伪装为成功", () => {
  const files = parseRepairDiff(
    createTwoFilesPatch(
      "a/app.py",
      "b/app.py",
      "return value",
      "return escape(value)",
    ),
  )
  assert.equal(files[0].removed, 1)
  assert.equal(files[0].added, 1)
  assert.ok(files[0].rows.some((row) => row.note))
  assert.throws(() => parseRepairDiff(""), /为空/)
  assert.throws(() => parseRepairDiff("not a patch"), /无法识别/)
})
test("文件删除及远距离修改保留真实位置，不拼接成连续源码", () => {
  const deleted = parseRepairDiff(
    createTwoFilesPatch("a/obsolete.py", "/dev/null", "legacy = True\n", ""),
  )[0]
  assert.equal(deleted.name, "obsolete.py")
  assert.equal(deleted.added, 0)
  assert.equal(deleted.removed, 1)
  const oldLines = Array.from({ length: 30 }, (_, i) => `line_${i + 1}`)
  const newLines = [...oldLines]
  newLines[0] = "changed_1"
  newLines[29] = "changed_30"
  const file = parseRepairDiff(
    createTwoFilesPatch(
      "a/app.py",
      "b/app.py",
      `${oldLines.join("\n")}\n`,
      `${newLines.join("\n")}\n`,
      "",
      "",
      { context: 2 },
    ),
  )[0]
  assert.equal(file.rows.filter((row) => row.section).length, 2)
  assert.deepEqual(
    file.rows.flatMap((row) => (row.after?.changed ? [row.after.number] : [])),
    [1, 30],
  )
})
