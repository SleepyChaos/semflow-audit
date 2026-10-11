import {createFileRoute} from "@tanstack/react-router"
import {PageHeader} from "@/features/shell/PageHeader"
export const Route=createFileRoute("/_layout/knowledge")({validateSearch:(s:Record<string,unknown>):{auditId?:string}=>({auditId:typeof s.auditId==="string"?s.auditId:undefined}),component:()=> <PageHeader title="知识库" description="管理参考资料与完整规则范例"/>})
