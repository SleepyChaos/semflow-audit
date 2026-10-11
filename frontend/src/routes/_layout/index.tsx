import {createFileRoute} from "@tanstack/react-router"
import {PageHeader} from "@/features/shell/PageHeader"
export const Route=createFileRoute("/_layout/")({component:()=> <PageHeader title="审计总览" description="查看任务、待办与规则沉淀"/>})
