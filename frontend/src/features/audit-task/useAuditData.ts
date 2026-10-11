import { useQuery } from "@tanstack/react-query"
import { getRuns } from "@/api/audits"
import { getCandidates, getCapabilities, getStages } from "@/api/stages"
export function useAudits() {
  return useQuery({
    queryKey: ["audits"],
    queryFn: getRuns,
    retry: 1,
    refetchInterval: (query) =>
      query.state.data?.some((run) =>
        ["queued", "running"].includes(run.status),
      )
        ? 2500
        : false,
  })
}
export function useAuditData(auditId: string) {
  const audits = useAudits()
  const run = audits.data?.find((item) => item.id === auditId)
  const stages = useQuery({
    queryKey: ["stages", auditId],
    queryFn: () => getStages(auditId),
    enabled: Boolean(run),
    retry: 1,
    refetchInterval: (query) =>
      query.state.data?.some((stage) =>
        ["queued", "running"].includes(stage.status),
      )
        ? 2500
        : false,
  })
  const busy =
    run?.status === "running" ||
    stages.data?.some((stage) => ["queued", "running"].includes(stage.status))
  const candidates = useQuery({
    queryKey: ["candidates", auditId],
    queryFn: () => getCandidates(auditId),
    enabled: Boolean(run),
    retry: false,
    refetchInterval: busy ? 3000 : false,
  })
  const capabilities = useQuery({
    queryKey: ["capabilities"],
    queryFn: getCapabilities,
    retry: 1,
    staleTime: 15000,
  })
  return { run, audits, stages, candidates, capabilities }
}
