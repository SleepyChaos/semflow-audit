import { useQueries } from "@tanstack/react-query"
import { useMemo } from "react"
import type { AuditRun } from "@/api/audits"
import { getCandidates } from "@/api/stages"
import { summarizeCandidates } from "./task-summary"
export function useRunSummaries(runs: AuditRun[]) {
  const limited = useMemo(() => {
    let active = 0
    const waiting: Array<() => void> = []
    return async (id: string) => {
      if (active >= 4)
        await new Promise<void>((resolve) => waiting.push(resolve))
      active++
      try {
        return await getCandidates(id)
      } finally {
        active--
        waiting.shift()?.()
      }
    }
  }, [])
  const queries = useQueries({
    queries: runs.map((run) => ({
      queryKey: ["candidates", run.id],
      queryFn: () => limited(run.id),
      retry: false,
      refetchInterval: ["queued", "running"].includes(run.status)
        ? 3000
        : false,
    })),
  })
  return runs.map((run, index) => ({
    run,
    query: queries[index],
    summary: queries[index].isSuccess
      ? summarizeCandidates(queries[index].data)
      : undefined,
  }))
}
