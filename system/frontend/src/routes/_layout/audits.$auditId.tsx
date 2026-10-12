import { createFileRoute } from "@tanstack/react-router"
import { AuditDetailPage } from "@/features/audit-task/AuditDetailPage"
import { normalizeStage } from "@/features/shell/navigation"
export const Route = createFileRoute("/_layout/audits/$auditId")({
  validateSearch: (search: Record<string, unknown>) => ({
    stage: normalizeStage(search.stage),
  }),
  component: AuditRoute,
})
function AuditRoute() {
  const { auditId } = Route.useParams()
  const { stage } = Route.useSearch()
  return <AuditDetailPage auditId={auditId} stage={stage} />
}
