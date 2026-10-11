import {useState} from "react"
import {Link} from "@tanstack/react-router"
import {Button} from "@/components/ui/button"
import {PageHeader} from "@/features/shell/PageHeader"
import {useAudits} from "./useAuditData"
import {RunList} from "./RunList"
export function AuditListPage(){
 const audits=useAudits(),[search,setSearch]=useState(""),[language,setLanguage]=useState("all"),[status,setStatus]=useState("all")
 const runs=audits.data??[],filtered=runs.filter(r=>r.project_name.toLowerCase().includes(search.toLowerCase())&&(language==="all"||r.language===language)&&(status==="all"||r.status===status))
 return <div className="page-stack"><PageHeader title="审计任务" description="管理源码扫描、候选复核和后续处理" actions={<Link to="/audits/new" className="button-link">新建审计</Link>}/>
 <div className="filter-bar"><input aria-label="搜索项目" placeholder="搜索项目名称…" value={search} onChange={e=>setSearch(e.target.value)}/><select aria-label="筛选语言" value={language} onChange={e=>setLanguage(e.target.value)}><option value="all">所有语言</option><option value="python">Python</option><option value="javascript">JavaScript / TypeScript</option></select><select aria-label="筛选扫描状态" value={status} onChange={e=>setStatus(e.target.value)}><option value="all">所有扫描状态</option><option value="completed">扫描完成</option><option value="running">扫描中</option><option value="failed">扫描失败</option><option value="queued">等待扫描</option><option value="cancelled">已取消</option></select><Button variant="outline" onClick={()=>audits.refetch()}>刷新</Button></div>
 {audits.isPending?<p role="status">正在读取任务…</p>:audits.error?<p role="alert">无法读取任务：{audits.error.message}</p>:runs.length&&!filtered.length?<div className="empty-state">没有符合筛选条件的任务</div>:<RunList runs={filtered}/>}
 <p className="page-note">静态告警来自 CodeQL；AI 候选需要复核，只有人工确认计入已确认缺陷。</p></div>
}
