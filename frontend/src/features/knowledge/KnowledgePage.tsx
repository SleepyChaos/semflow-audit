import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query"
import {Link} from "@tanstack/react-router"
import {useState} from "react"
import {toast} from "sonner"
import {getCapabilities,getKnowledge,indexKnowledge} from "@/api/stages"
import {Button} from "@/components/ui/button"
import {PageHeader} from "@/features/shell/PageHeader"
import {KnowledgePanel} from "./KnowledgePanel"
const corpusName:Record<string,string>={reference:"参考知识 / API",rule_example:"完整规则范例"}
export function KnowledgePage({auditId}:{auditId?:string}){
 const [language,setLanguage]=useState("all"),[corpus,setCorpus]=useState("all"),[importOpen,setImportOpen]=useState(false),[importLanguage,setImportLanguage]=useState("python")
 const cache=useQueryClient(),docs=useQuery({queryKey:["knowledge"],queryFn:getKnowledge,retry:1,refetchInterval:15000}),cap=useQuery({queryKey:["capabilities"],queryFn:getCapabilities,retry:1})
 const index=useMutation({mutationFn:indexKnowledge,onSuccess:()=>{cache.invalidateQueries({queryKey:["knowledge"]});toast.success("向量索引已排队")},onError:(error:Error)=>toast.error(error.message)})
 const filtered=docs.data?.filter(d=>(language==="all"||[language,"any"].includes(d.language))&&(corpus==="all"||d.corpus===corpus))??[]
 return <div className="page-stack"><PageHeader title="知识库" description="管理 RAG 参考资料、API 版本与完整规则范例" actions={<Button onClick={()=>setImportOpen(!importOpen)}>{importOpen?"收起导入":"导入知识"}</Button>}/>
 {auditId&&<Link className="text-action" to="/audits/$auditId" params={{auditId}} search={{stage:"rules"}}>返回 RAG 规则</Link>}
 <div className="info-strip"><span>检索能力</span><p>{cap.isPending?"读取中":cap.error?"能力读取失败":cap.data?.embedding_model?`BM25 + 向量检索 · ${cap.data.embedding_model}`:"BM25 可用 · 未配置向量模型，已保存资料仍可检索"}。规则生成需要匹配语言库版本的参考知识和完整范例。</p></div>
 {importOpen&&<div className="knowledge-import"><div className="section-heading"><h2>导入资料</h2><select className="native-select" aria-label="导入资料语言" value={importLanguage} onChange={e=>setImportLanguage(e.target.value)}><option value="python">Python</option><option value="javascript">JavaScript</option><option value="any">通用知识</option></select></div><KnowledgePanel key={importLanguage} language={importLanguage} embeddingReady={Boolean(cap.data?.embedding_model)} embedded/></div>}
 <div className="filter-bar"><select aria-label="知识语言" value={language} onChange={e=>setLanguage(e.target.value)}><option value="all">所有语言</option><option value="python">Python</option><option value="javascript">JavaScript</option></select><select aria-label="材料类型" value={corpus} onChange={e=>setCorpus(e.target.value)}><option value="all">所有材料类型</option><option value="reference">参考知识 / API</option><option value="rule_example">完整规则范例</option></select><span className="filter-count">{filtered.length} 份资料</span><Button variant="outline" onClick={()=>docs.refetch()}>刷新</Button></div>
 {docs.isPending?<p>正在读取知识资料…</p>:docs.error?<p role="alert">资料读取失败：{docs.error.message}</p>:!filtered.length?<div className="empty-state"><h2>暂无匹配资料</h2><p>通过上方“导入知识”添加正文，或使用本地官方资料导入脚本。</p></div>:<div className="knowledge-list">{filtered.map(d=><article key={d.document_id} className="knowledge-document"><div><span className="eyebrow">{d.language.toUpperCase()} / {corpusName[d.corpus]??d.corpus}</span><h3>{d.title}</h3><p className="document-source">{d.source}</p><p className="page-note">正文哈希 {d.version.slice(0,16)} · {d.chunks} 片段 · 已保存 / BM25 可用</p></div><div className="document-index"><span className="status-label">{d.indexed_chunks}/{d.chunks} 已向量化</span>{!d.shared&&<Button size="sm" variant="outline" disabled={!cap.data?.embedding_model||index.isPending} onClick={()=>index.mutate(d.document_id)}>建立向量索引</Button>}{d.index_error&&<p role="alert">索引失败：{d.index_error}</p>}</div></article>)}</div>}
 {index.error&&<p role="alert">索引请求失败：{index.error.message}</p>}</div>
}
