import { apiJson } from "./backend"
import type { Candidate } from "./stages"

// Repeated executions keep every record; resolve differing human states using
// actual decision history, not the candidate creation order.
export async function attachDecisionTimes(candidates: Candidate[]) {
  const groups = new Map<string, Candidate[]>()
  for (const candidate of candidates) {
    const key = candidate.identity_key || candidate.id
    const group = groups.get(key) ?? []
    group.push(candidate)
    groups.set(key, group)
  }
  const conflicted = [...groups.values()]
    .filter((group) => new Set(group.map((c) => c.status)).size > 1)
    .flat()
  const times = new Map<string, string>()
  for (let start = 0; start < conflicted.length; start += 4) {
    await Promise.all(
      conflicted.slice(start, start + 4).map(async (candidate) => {
        const decisions = await apiJson<{ created_at: string }[]>(
          `/candidates/${candidate.id}/decisions`,
        )
        const latest = decisions.reduce<string | undefined>(
          (best, decision) =>
            Number.isFinite(Date.parse(decision.created_at)) &&
            (!best || Date.parse(decision.created_at) > Date.parse(best))
              ? decision.created_at
              : best,
          undefined,
        )
        if (latest) times.set(candidate.id, latest)
      }),
    )
  }
  return candidates.map((candidate) =>
    times.has(candidate.id)
      ? { ...candidate, latest_decision_at: times.get(candidate.id) }
      : candidate,
  )
}
