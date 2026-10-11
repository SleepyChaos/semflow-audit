import {createFileRoute} from "@tanstack/react-router"
import {PageHeader} from "@/features/shell/PageHeader"
export const Route=createFileRoute("/_layout/rules")({validateSearch:(s:Record<string,unknown>):{ruleId?:string}=>({ruleId:typeof s.ruleId==="string"?s.ruleId:undefined}),component:()=> <PageHeader title="规则库" description="查看规则、验证记录与发布状态"/>})
