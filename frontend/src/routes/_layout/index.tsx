import { createFileRoute } from "@tanstack/react-router"
import { Workbench } from "@/features/audit-task/Workbench"
export const Route = createFileRoute("/_layout/")({
  component: Workbench,
  head: () => ({ meta: [{ title: "审计工作台 · AI Code Audit" }] }),
})
