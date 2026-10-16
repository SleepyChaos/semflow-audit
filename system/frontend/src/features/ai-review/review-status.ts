import type { Candidate } from "@/api/stages"

export function reviewVerdict(candidate: Candidate) {
  if (candidate.classification?.source === "human") {
    if (candidate.classification.status === "confirmed")
      return { tone: "supported", label: "确认真实" }
    if (candidate.classification.status === "excluded")
      return { tone: "excluded", label: "确认误报" }
    if (candidate.classification.status === "insufficient")
      return { tone: "insufficient", label: "证据不足" }
  }
  const status = candidate.review?.status
  if (status === "supported") return { tone: "supported", label: "确认真实" }
  if (status === "excluded") return { tone: "excluded", label: "确认误报" }
  if (status === "reviewing") return { tone: "neutral", label: "复核中" }
  if (status) return { tone: "insufficient", label: "证据不足" }
  return { tone: "neutral", label: "待复核" }
}

export function currentReviewCandidates(candidates: Candidate[]) {
  const byIdentity = new Map<string, Candidate>()
  // The API orders immutable attempts by creation time; display the newest review
  // for each identity, while retaining prior human decisions in execution history.
  for (const candidate of candidates) {
    const key = candidate.identity_key || candidate.id
    const previous = byIdentity.get(key)
    if (!previous || candidate.review || !previous.review)
      byIdentity.set(key, candidate)
  }
  const priority: Record<string, number> = {
    supported: 0,
    insufficient: 1,
    neutral: 1,
    excluded: 2,
  }
  return [...byIdentity.values()].sort(
    (a, b) => priority[reviewVerdict(a).tone] - priority[reviewVerdict(b).tone],
  )
}
