import { Button } from "@/components/ui/button"
export function ReviewControls({
  disabled,
  reason,
  pending,
  onStart,
}: {
  disabled: boolean
  reason: string | null
  pending: boolean
  onStart: () => void
}) {
  return (
    <div className="review-controls">
      <div className="action-banner">
        <div>
          <h3>统一复核</h3>
          <p>
            汇合 CodeQL 与 AI
            初审结果，自动区分真实、误报和证据不足，并生成每项的项目描述、利用用例与关联源码。
          </p>
          {reason && <p className="action-hint">{reason}</p>}
        </div>
        <div className="review-flow-actions">
          <Button disabled={disabled || pending} onClick={onStart}>
            {pending ? "正在提交…" : "启动统一复核"}
          </Button>
        </div>
      </div>
    </div>
  )
}
