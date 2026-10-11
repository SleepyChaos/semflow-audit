import type {RuleVersion} from "@/api/stages"
const names:Record<string,string>={passed:"通过",failed:"失败",target_detected:"目标根因已确认",candidate_match_needs_confirmation:"命中候选，待确认根因",baseline_match_needs_confirmation:"与基线相近，待确认",not_evaluated:"未评估",missing:"缺失",legacy_not_evaluated:"历史版本未评估"}
function status(value:unknown){if(typeof value==="string")return names[value]??value;if(value&&typeof value==="object"&&"status" in value)return status(value.status);return "未运行"}
export function RuleValidationSummary({rule}:{rule:RuleVersion}){
 return <div className="validation-summary" aria-label="规则验收摘要">{[
 ["编译",status(rule.validation.compile)],["开发样本",status(rule.validation.development)],["独立测试",status(rule.validation.independent_holdout)],["项目回扫",status(rule.validation.project_replay)],["样本人工批准",rule.fixtures_approved?"已批准":"待批准"],["发布",rule.status==="published"?"已发布":rule.status==="validated"?"已验证，待发布":"尚不可发布"]
 ].map(([label,value])=><div key={label}><span>{label}：{value}</span></div>)}</div>
}
