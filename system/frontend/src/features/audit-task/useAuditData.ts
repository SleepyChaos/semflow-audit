import { useQuery } from "@tanstack/react-query"
import { getRun, getRuns } from "@/api/audits"
import { getCandidates, getCapabilities, getStages } from "@/api/stages"
import { useDiscoveryRefresh } from "./useDiscoveryRefresh"
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
export function useAudit(auditId: string | null) {
  return useQuery({
    queryKey: ["audit", auditId],
    queryFn: () => getRun(auditId!),
    enabled: Boolean(auditId),
    retry: 1,
    refetchInterval: (query) =>
      query.state.data &&
      ["queued", "running"].includes(query.state.data.status)
        ? 2500
        : false,
  })
}
export function useAuditData(auditId: string) {
  const audit = useAudit(auditId)
  const run = audit.data
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
  useDiscoveryRefresh([
    ...(run ? [{ key: `audit:${auditId}`, auditId, status: run.status }] : []),
    ...(stages.data ?? []).map((stage) => ({
      key: `stage:${stage.id}`,
      auditId,
      status: stage.status,
    })),
  ])
  const busy =
    ["queued", "running"].includes(run?.status ?? "") ||
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
  return { run, audit, stages, candidates, capabilities }
}
