import { useQuery } from "@tanstack/react-query"
import { getEnvironment } from "@/api/audits"
import { getCapabilities } from "@/api/stages"
import { Dialog,DialogContent,DialogDescription,DialogHeader,DialogTitle } from "@/components/ui/dialog"
export function EnvironmentDrawer({open,onOpenChange}:{open:boolean;onOpenChange:(open:boolean)=>void}) {
 const environment=useQuery({queryKey:["environment"],queryFn:getEnvironment,enabled:open})
 const capabilities=useQuery({queryKey:["capabilities"],queryFn:getCapabilities,enabled:open})
 return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent><DialogHeader><DialogTitle>执行环境</DialogTitle><DialogDescription>扫描、模型与检索的实际连接状态</DialogDescription></DialogHeader>
 {environment.error?<p role="alert">{environment.error.message}</p>:null}
 <dl className="environment-details"><dt>CodeQL</dt><dd>{environment.data?.codeql_version??"检查中或不可用"}</dd><dt>查询包</dt><dd>{environment.data?environment.data.query_packs_present?"已安装":"未安装":"检查中"}</dd><dt>任务队列</dt><dd>{environment.data?environment.data.queue_available?"已连接":"未连接":"检查中"}</dd><dt>模型服务</dt><dd>{capabilities.data?capabilities.data.model_configured?"已配置":"未配置":"检查中"}</dd><dt>检索方式</dt><dd>{capabilities.data?.retrieval??"检查中"}</dd></dl>
 {capabilities.error?<p role="alert">{capabilities.error.message}</p>:null}<p className="muted-copy">新版独立工作台 · 前端 5174 / API 8001</p>
 </DialogContent></Dialog>
}
