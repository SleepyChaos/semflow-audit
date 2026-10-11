import {createFileRoute} from "@tanstack/react-router"
import {KnowledgePage} from "@/features/knowledge/KnowledgePage"
export const Route=createFileRoute("/_layout/knowledge")({validateSearch:(s:Record<string,unknown>):{auditId?:string}=>({auditId:typeof s.auditId==="string"?s.auditId:undefined}),component:()=> <KnowledgePage auditId={Route.useSearch().auditId}/>})
