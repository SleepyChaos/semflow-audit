import {createFileRoute} from "@tanstack/react-router"
import {PageHeader} from "@/features/shell/PageHeader"
export const Route=createFileRoute("/_layout/audits/new")({component:()=> <PageHeader title="新建审计" description="上传源码 ZIP，创建独立审计任务"/>})
