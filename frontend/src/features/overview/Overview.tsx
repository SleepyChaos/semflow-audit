import {useQuery} from "@tanstack/react-query"
import {Link} from "@tanstack/react-router"
import {getRules} from "@/api/stages"
import {Button} from "@/components/ui/button"
import {useAudits} from "@/features/audit-task/useAuditData"
import {useRunSummaries} from "@/features/audit-task/useRunSummaries"
import {RunList} from "@/features/audit-task/RunList"
import {PageHeader} from "@/features/shell/PageHeader"
export function Overview(){
 const audits=useAudits(),runs=audits.data??[],summaries=useRunSummaries(runs)
 const rules=useQuery({queryKey:["rules","published"],queryFn:()=>getRules(undefined,true),retry:1})
 const pending=audits.isPending||summaries.some(s=>s.query.isPending)?"统计中":audits.isError||summaries.some(s=>s.query.isError)?"无法统计":summaries.reduce((n,s)=>n+(s.summary?.pending??0),0)
 const count=(n:number)=>audits.isPending?"统计中":audits.isError?"无法统计":n
 return <div className="page-stack"><PageHeader title="审计总览" description="从源码到证据、修复与规则，掌握每个任务的当前状态" actions={<Button variant="outline" onClick={()=>{audits.refetch();rules.refetch();for(const s of summaries)s.query.refetch()}}>刷新</Button>}/>
 <div className="overview-intro"><div><span className="eyebrow">SECURITY WORKSPACE</span><h2>让每一次发现，都有证据可查。</h2><p>选择一个项目继续处理，或上传源码开始新的审计。</p></div><Link className="button-link" to="/audits/new">＋ 新建审计</Link></div>
 <div className="metric-grid">{[["审计任务",count(runs.length)],["正在扫描",count(runs.filter(r=>["queued","running"].includes(r.status)).length)],["待人工判断",pending],["已发布规则",rules.isPending?"统计中":rules.isError?"无法统计":rules.data.length]].map(([label,value])=><div className="metric" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
 {audits.error&&<p role="alert">任务读取失败：{audits.error.message}</p>}
 <section><div className="section-heading"><h2>最近任务</h2><Link to="/audits">查看全部 →</Link></div>{audits.isPending?<p>正在读取任务…</p>:!audits.error&&<RunList runs={runs.slice(0,5)}/>}</section>
 <div className="info-strip"><span>审计提示</span><p>扫描完成表示引擎执行结束。未报警或已检查的代码，仍可能存在尚未确认的业务风险。</p></div></div>
}
