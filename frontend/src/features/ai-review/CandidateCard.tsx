import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query"
import {useState} from "react"
import {toast} from "sonner"
import {type Candidate,decideCandidate,type Evidence,getDecisions,type StageRun} from "@/api/stages"
import {Button} from "@/components/ui/button"
import {Checkbox} from "@/components/ui/checkbox"
export function CandidateCard({candidate,evidence,busy,stages=[]}:{candidate:Candidate;evidence:Evidence[];busy:boolean;stages?:StageRun[]}){
 const [reason,setReason]=useState(""),[status,setStatus]=useState("confirmed"),[ids,setIds]=useState(candidate.evidence_ids),[history,setHistory]=useState(false)
 const cache=useQueryClient()
 const decisions=useQuery({queryKey:["decisions",candidate.id],queryFn:()=>getDecisions(candidate.id),enabled:history})
 const mutation=useMutation({mutationFn:()=>decideCandidate(candidate.id,{status,reason,evidence_ids:ids}),onSuccess:async()=>{await cache.invalidateQueries();setReason("");toast.success("人工判断已记录")},onError:(error:Error)=>toast.error(error.message)})
 const hasSource=evidence.some(e=>ids.includes(e.id)&&["code","query"].includes(e.kind))
 const missing=["confirmed","excluded"].includes(status)&&!hasSource?"请选择至少一条源码或查询证据":reason.trim().length<10?"请填写至少 10 个字符的判断理由":busy?"等待当前执行结束":null
 const batches=stages.filter(s=>s.kind==="review").flatMap(s=>Array.isArray(s.result.batches)?s.result.batches:[])
 const assessment=batches.flatMap(b=>Array.isArray(b.assessments)?b.assessments:[]).find(a=>a.candidate_id===candidate.id)
 return <article className="candidate-card evidence-workspace"><header><div><span className="eyebrow">{candidate.weakness} / {candidate.origin==="ai"?"AI 候选":"静态告警"}</span><h3>{candidate.title}</h3></div><span className="status-label">{{confirmed:"已确认",excluded:"支持排除",pending:"待确认",insufficient:"证据不足"}[candidate.status]??candidate.status}</span></header>
 <p>{candidate.description}</p><div className="assessment-strip"><span>原始模型建议：{candidate.model_assessment==="unknown"?"未知（unknown）":candidate.model_assessment}</span>{assessment&&<span>复核历史建议：{String(assessment.assessment)}（建议）</span>}</div>
 <h4>源码与判断依据</h4><p className="page-note">勾选所依据的证据，再记录人工判断。仅人工确认计入已确认缺陷。</p>
 {!evidence.length&&<p role="status">暂无可用证据，可从高级选项补充源码。</p>}
 {evidence.map(item=><div className="evidence-choice" key={item.id}><label className="stage-check" htmlFor={`candidate-${candidate.id}-${item.id}`}><Checkbox aria-label={`${item.kind === "code" ? "源码" : item.kind === "query" ? "查询" : item.kind} · ${String(item.reference.file ?? item.reference.rule_version ?? item.id)}`} id={`candidate-${candidate.id}-${item.id}`} checked={ids.includes(item.id)} onCheckedChange={checked=>setIds(checked?[...ids,item.id]:ids.filter(id=>id!==item.id))}/><span>{item.kind==="code"?"源码":item.kind==="query"?"查询":item.kind} · {String(item.reference.file??item.reference.rule_version??item.id)}</span><small>{candidate.evidence_ids.includes(item.id)?"关联证据":"补充证据"}</small></label><pre className="source-code">{item.content}</pre><p className="evidence-digest">快照 {item.snapshot_hash.slice(0,16)} · SHA256 {item.digest.slice(0,16)}</p></div>)}
 <div className="decision-form"><label>人工判断状态<select className="native-select" aria-label="人工判断状态" value={status} onChange={e=>setStatus(e.target.value)}><option value="confirmed">已确认</option><option value="excluded">支持排除</option><option value="pending">待确认</option><option value="insufficient">证据不足</option></select></label><label>判断理由（至少 10 个字符）<textarea className="audit-textarea" value={reason} onChange={e=>setReason(e.target.value)} maxLength={4000}/></label>{missing&&<p role="status" className="action-hint">{missing}</p>}{mutation.error&&<p role="alert">记录失败：{mutation.error.message}，判断输入已保留。</p>}<Button disabled={Boolean(missing)||mutation.isPending} onClick={()=>mutation.mutate()}>记录人工判断</Button></div>
 <Button variant="ghost" size="sm" onClick={()=>setHistory(!history)}>判断历史</Button>{history&&<div>{decisions.isPending?<p>正在读取判断历史…</p>:decisions.error?<p role="alert">{decisions.error.message}</p>:<pre className="source-code">{JSON.stringify(decisions.data,null,2)}</pre>}</div>}</article>
}
