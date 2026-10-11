import {useQuery} from "@tanstack/react-query"
import {Link} from "@tanstack/react-router"
import {useEffect,useState} from "react"
import {getRules} from "@/api/stages"
import {Button} from "@/components/ui/button"
import {PageHeader} from "@/features/shell/PageHeader"
import {RuleCard} from "./RuleCard"
export function RulesPage({ruleId}:{ruleId?:string}){
 const [language,setLanguage]=useState("all"),[purpose,setPurpose]=useState("all"),[status,setStatus]=useState("all"),[search,setSearch]=useState("")
 const rules=useQuery({queryKey:["rules","all"],queryFn:()=>getRules(),retry:1,refetchInterval:15000})
 useEffect(()=>{if(ruleId&&rules.data)document.getElementById("rule-"+ruleId)?.scrollIntoView({block:"start"})},[ruleId,rules.data])
 const filtered=rules.data?.filter(r=>(language==="all"||r.language===language)&&(purpose==="all"||r.purpose===purpose)&&(status==="all"||r.status===status)&&r.title.toLowerCase().includes(search.toLowerCase()))??[]
 return <div className="page-stack"><PageHeader title="规则库" description="查看规则版本、真实验收与发布状态" actions={<Button variant="outline" onClick={()=>rules.refetch()}>刷新</Button>}/><div className="filter-bar"><input aria-label="搜索规则" placeholder="搜索规则…" value={search} onChange={e=>setSearch(e.target.value)}/><select aria-label="规则语言" value={language} onChange={e=>setLanguage(e.target.value)}><option value="all">所有语言</option><option value="python">Python</option><option value="javascript">JS / TS</option></select><select aria-label="筛选规则用途" value={purpose} onChange={e=>setPurpose(e.target.value)}><option value="all">所有用途</option><option value="review_anchor">复审锚点</option><option value="vulnerability_detector">漏洞检测</option><option value="framework_model">框架建模</option></select><select aria-label="规则状态" value={status} onChange={e=>setStatus(e.target.value)}><option value="all">所有状态</option><option value="draft">草稿</option><option value="validated">已验证</option><option value="published">已发布</option><option value="retired">已停用</option></select></div>
 {rules.isPending?<p>正在读取规则…</p>:rules.error?<p role="alert">规则读取失败：{rules.error.message}</p>:!filtered.length?<div className="empty-state"><h2>暂无符合条件的规则</h2><p>进入一个审计任务的 RAG 规则页面，描述覆盖缺口并生成版本。</p><Link to="/audits" className="button-link">选择审计任务</Link></div>:filtered.map(r=><RuleCard key={r.id} rule={r} awaiting={r.status==="draft"&&!r.fixtures_approved}/>)}</div>
}
