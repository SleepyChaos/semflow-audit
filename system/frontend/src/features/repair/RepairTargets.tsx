import { Link } from "@tanstack/react-router"
import type { Candidate } from "@/api/stages"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"

export function RepairTargets({
  auditId,
  candidates,
  selected,
  onSelect,
  busy,
}: {
  auditId: string
  candidates: Candidate[]
  selected: string[]
  onSelect: (value: string[]) => void
  busy: boolean
}) {
  return (
    <section className="repair-targets" aria-label="选择修复目标">
      <div className="downstream-section-heading">
        <div>
          <h3>选择要修复的漏洞</h3>
          <p>仅列出分类为真实的漏洞，关联文件由平台读取。</p>
        </div>
        <div className="stage-row">
          <span className="selection-count">
            已选 {selected.length} / {candidates.length}
          </span>
          <Button
            variant="ghost"
            size="sm"
            disabled={busy || !candidates.length}
            onClick={() =>
              onSelect(
                selected.length === candidates.length
                  ? []
                  : candidates.map((item) => item.id),
              )
            }
          >
            {selected.length === candidates.length && candidates.length
              ? "取消全选"
              : "全选"}
          </Button>
        </div>
      </div>
      {candidates.length ? (
        <div className="repair-target-grid">
          {candidates.map((item) => (
            <label
              className="repair-target"
              htmlFor={`repair-target-${item.id}`}
              data-selected={selected.includes(item.id)}
              key={item.id}
            >
              <Checkbox
                id={`repair-target-${item.id}`}
                checked={selected.includes(item.id)}
                aria-label={item.review?.detail?.title ?? item.title}
                disabled={busy}
                onCheckedChange={(checked) =>
                  onSelect(
                    checked
                      ? [...selected, item.id]
                      : selected.filter((id) => id !== item.id),
                  )
                }
              />
              <span>
                <strong>{item.review?.detail?.title ?? item.title}</strong>
                <small>
                  {item.location.file ?? "位置待核实"}:
                  {item.location.line ?? "—"} · {item.weakness}
                </small>
              </span>
            </label>
          ))}
        </div>
      ) : (
        <div className="downstream-empty">
          <h4>还没有可修复的真实漏洞</h4>
          <p>先完成 AI 复核或调整分类，再选择修复目标。</p>
          <Button asChild variant="outline">
            <Link
              to="/audits/$auditId"
              params={{ auditId }}
              search={{ stage: "review" }}
            >
              查看复核结果
            </Link>
          </Button>
        </div>
      )}
    </section>
  )
}
