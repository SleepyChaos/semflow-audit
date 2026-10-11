import type { AuditRun } from "@/api/audits"
import type { Candidate, RuleVersion, StageRun } from "@/api/stages"
import type { AuditStage } from "@/features/shell/navigation"
export function uniqueCandidates(candidates:Candidate[]) {
 const identities=new Map<string,Candidate>()
 for(const candidate of candidates){
  const key=candidate.identity_key||candidate.id,previous=identities.get(key)
  if(!previous||(previous.status==="pending"&&candidate.status!=="pending")||previous.status===candidate.status)identities.set(key,candidate)
 }
 return [...identities.values()]
}
export function summarizeCandidates(candidates:Candidate[]){
 const unique=uniqueCandidates(candidates)
 return {aiCandidates:unique.filter(c=>c.origin==="ai").length,confirmed:unique.filter(c=>c.status==="confirmed").length,pending:unique.filter(c=>["pending","insufficient"].includes(c.status)).length}
}
export const runStatuses:Record<string,string>={queued:"等待扫描",running:"扫描中",completed:"扫描完成",failed:"扫描失败",cancelled:"已取消"}
export function getTaskAction(run:AuditRun,candidates:Candidate[]|undefined,stages?:StageRun[],rules?:RuleVersion[]):{label:string;stage:AuditStage;reason:string}|null{
 const active=stages?.find(s=>["queued","running","awaiting_confirmation"].includes(s.status))
 if(active)return {label:"查看当前执行",stage:active.kind==="rule"?"rules":active.kind==="repair"?"repair":"review",reason:"当前阶段仍在执行或等待人工确认"}
 if(["queued","running","failed","cancelled"].includes(run.status)&&!run.coverage.dual_engine?.review_ready)return {label:"查看扫描",stage:"scan",reason:runStatuses[run.status]??run.status}
 if(candidates===undefined)return {label:"查看候选",stage:"review",reason:"候选数量尚未读取"}
 const summary=summarizeCandidates(candidates)
 if(summary.pending)return {label:"复核候选",stage:"review",reason:`还有 ${summary.pending} 个候选需要人工判断`}
 if(rules?.some(r=>r.audit_id===run.id&&!["published","retired"].includes(r.status)))return {label:"查看规则验收",stage:"rules",reason:"生成规则仍需验证与人工验收"}
 if(summary.confirmed)return {label:"修复与导出",stage:"repair",reason:`已人工确认 ${summary.confirmed} 个缺陷`}
 return {label:"查看复核",stage:"review",reason:"扫描完成不代表业务流程安全"}
}
