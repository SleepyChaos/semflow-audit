import {useNavigate} from "@tanstack/react-router"
import {PageHeader} from "@/features/shell/PageHeader"
import {UploadForm} from "@/features/upload/UploadForm"
export function NewAuditPage({ruleId}:{ruleId?:string}){
 const navigate=useNavigate()
 return <div className="page-stack upload-page"><PageHeader title="新建审计" description="上传源码快照，CodeQL 与 AI 独立粗筛将并行启动"/><UploadForm initialRuleId={ruleId} onCreated={id=>navigate({to:"/audits/$auditId",params:{auditId:id},search:{stage:"scan"}})}/></div>
}
