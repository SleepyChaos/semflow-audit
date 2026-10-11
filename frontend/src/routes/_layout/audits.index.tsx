import {createFileRoute} from "@tanstack/react-router"
import {AuditListPage} from "@/features/audit-task/AuditListPage"
export const Route=createFileRoute("/_layout/audits/")({component:AuditListPage})
