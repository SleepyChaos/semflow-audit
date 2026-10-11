import { Link,useNavigate } from "@tanstack/react-router"
import { RunDetails } from "@/features/codeql-stage/RunDetails"
import { PageHeader } from "@/features/shell/PageHeader"
import { auditStages,normalizeStage,stagePanels,type AuditStage } from "@/features/shell/navigation"
import { useAuditData } from "./useAuditData"
export function AuditDetailPage({auditId,stage}:{auditId:string;stage:AuditStage}) {
 const data=useAuditData(auditId)
 const navigate=useNavigate()
 const changeStage=(next:AuditStage)=>navigate({to:"/audits/$auditId",params:{auditId},search:{stage:next}})
 if(data.audits.isPending)return <p role="status">正在读取审计任务…</p>
 if(data.audits.error)return <div role="alert"><h1>无法读取审计任务</h1><p>{data.audits.error.message}</p><button type="button" onClick={()=>data.audits.refetch()}>重新读取</button></div>
 if(!data.run)return <div className="empty-state"><h1>未找到审计任务</h1><p>任务可能不属于当前独立工作台。</p><Link to="/audits">返回任务列表</Link></div>
 const selected=auditStages.find(item=>item.id===stage)!
 const reverse:Record<string,AuditStage>={codeql:"scan",ai:"review",repair:"repair",rag:"rules"}
 return <div className="page-stack"><PageHeader title={selected.title} description={selected.description}/><RunDetails run={data.run} activeStage={stagePanels[stage]} onStageChange={value=>changeStage(normalizeStage(reverse[value]))} onCreated={id=>navigate({to:"/audits/$auditId",params:{auditId:id},search:{stage:"scan"}})}/></div>
}
