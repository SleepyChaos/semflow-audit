import {Button} from "@/components/ui/button"
export function ReviewControls({disabled,reason,pending,onStart,children}:{disabled:boolean;reason:string|null;pending:boolean;onStart:()=>void;children:React.ReactNode}){
 return <div className="review-controls"><div className="action-banner"><div><h3>统一复核</h3><p>汇合 CodeQL 告警与 AI 粗筛候选，检查前提和反证，再由人工作出判断。</p>{reason&&<p className="action-hint">{reason}</p>}</div><Button disabled={disabled||pending} onClick={onStart}>{pending?"正在提交…":"启动统一复核"}</Button></div><details className="advanced-options"><summary>高级选项与人工补充证据</summary>{children}</details></div>
}
