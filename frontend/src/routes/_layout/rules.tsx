import {createFileRoute} from "@tanstack/react-router"
import {RulesPage} from "@/features/rules/RulesPage"
export const Route=createFileRoute("/_layout/rules")({validateSearch:(s:Record<string,unknown>):{ruleId?:string}=>({ruleId:typeof s.ruleId==="string"?s.ruleId:undefined}),component:()=> <RulesPage ruleId={Route.useSearch().ruleId}/>})
