import {createFileRoute} from "@tanstack/react-router"
import {PageHeader} from "@/features/shell/PageHeader"
export const Route=createFileRoute("/_layout/audits/")({component:()=> <PageHeader title="审计任务" description="选择任务查看扫描、复核、修复与规则"/>})
