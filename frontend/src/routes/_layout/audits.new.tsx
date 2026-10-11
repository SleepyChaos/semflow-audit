import {createFileRoute} from "@tanstack/react-router"
import {NewAuditPage} from "@/features/audit-task/NewAuditPage"
export const Route=createFileRoute("/_layout/audits/new")({validateSearch:(search:Record<string,unknown>):{ruleId?:string}=>({ruleId:typeof search.ruleId==="string"?search.ruleId:undefined}),component:()=> <NewAuditPage ruleId={Route.useSearch().ruleId}/>})
