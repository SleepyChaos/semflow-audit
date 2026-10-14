export function checkTone(status: string) {
  if (/失败|未通过|受阻|缺失|failed|error|missing/.test(status))
    return "attention"
  if (/通过|已批准|已发布|已验证|已确认|passed|target_detected/.test(status))
    return "done"
  if (/正在|running|queued/.test(status)) return "active"
  return "waiting"
}
