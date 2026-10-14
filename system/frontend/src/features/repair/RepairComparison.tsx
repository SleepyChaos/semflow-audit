import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import {
  type RepairComparison as Comparison,
  verifyRepair,
} from "@/api/verification"
import { Button } from "@/components/ui/button"

const labels: Record<string, string> = {
  passed: "所列测试前后对比通过，待审阅",
  failed: "验证未通过",
  inconclusive: "验证证据不足",
  stale: "材料已变化，需重新验证",
  missing: "尚未进行前后对比",
  queued: "等待运行前后对比",
  running: "正在运行前后对比",
  cancelled: "验证已取消",
}
export function RepairComparison({
  id,
  comparison,
  suiteId,
  busy,
  accepted,
}: {
  id: string
  comparison?: Comparison
  suiteId: string
  busy: boolean
  accepted: boolean
}) {
  const cache = useQueryClient()
  const run = useMutation({
    mutationFn: () =>
      verifyRepair(id, suiteId || comparison?.identity?.suite_id || ""),
    onSuccess: () => cache.invalidateQueries(),
    onError: (error: Error) => toast.error(error.message),
  })
  const status = comparison?.status ?? "missing"
  return (
    <section className="repair-comparison" aria-label="修复前后验证">
      <h4>修复前后验证</h4>
      <p className="comparison-status" data-status={status}>
        {labels[status] ?? "验证状态待核实"}
      </p>
      <p>
        {comparison?.summary ??
          "语法通过或 AI 建议不能代替漏洞复现和修复后的实际测试。"}
      </p>
      {comparison?.error && <p role="alert">{comparison.error}</p>}
      {!!comparison?.cases?.length && (
        <div className="comparison-table-scroll">
          <table className="comparison-table">
            <thead>
              <tr>
                <th>测试及预期</th>
                <th>修复前</th>
                <th>补丁后</th>
                <th>判断依据</th>
              </tr>
            </thead>
            <tbody>
              {comparison.cases.map((test) => (
                <tr key={test.name}>
                  <td>
                    <strong>
                      {test.category === "security" ? "安全测试" : "正常功能"}
                    </strong>
                    <p>{test.input_description}</p>
                    <small>{test.expected_behavior}</small>
                  </td>
                  <td>
                    {test.category === "security" &&
                    test.before === "assertion_failed"
                      ? "已复现风险"
                      : test.before_label}
                  </td>
                  <td>{test.after_label}</td>
                  <td>{test.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {comparison?.repetitions && (
        <p className="page-note">
          同一组测试重复运行 {comparison.repetitions}{" "}
          轮。通过只覆盖列出的用例；未测试的业务路径与部署环境仍需核实。
        </p>
      )}
      {comparison?.suite_created_before_repair === false && (
        <p className="page-note">
          这份测试是在补丁之后准备的，请重点核对断言是否覆盖了原问题。
        </p>
      )}
      {!!comparison?.assumptions?.length && (
        <ul>
          {comparison.assumptions.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      )}
      {!!comparison?.runs && (
        <details>
          <summary>查看逐轮运行记录</summary>
          <pre className="source-code">
            {JSON.stringify(comparison.runs, null, 2)}
          </pre>
        </details>
      )}
      {!accepted && (
        <>
          <Button
            variant="outline"
            disabled={
              !(suiteId || comparison?.identity?.suite_id) ||
              busy ||
              run.isPending ||
              ["queued", "running"].includes(status)
            }
            onClick={() => run.mutate()}
          >
            运行修复前后对比
          </Button>
          {!suiteId && !comparison?.identity?.suite_id && (
            <p className="page-note">
              先在上方选择覆盖修复目标的项目验收测试集。
            </p>
          )}
        </>
      )}
      {run.error && <p role="alert">{run.error.message}</p>}
    </section>
  )
}
