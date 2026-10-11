import {expect,test} from "@playwright/test"
import {mockAuditApi} from "./fixtures/audit-api"
const rule={id:"rule-1",audit_id:"task-1",stage_id:"stage-1",title:"Flask 路由 XSS 检测",language:"python",purpose:"vulnerability_detector",holdout_id:null,strategy:"new_query",query:"import python",modules:{},query_hash:"abc",status:"draft",fixtures_approved:false,fixtures:{},validation:{compile:"passed"},retrieval:[]}
test("生成条件与缺少材料均直接说明",async({page})=>{
 await mockAuditApi(page,{"/audits/task-1/stages":[{id:"s",kind:"rule",status:"failed",phase:"queued",created_at:"2026-10-11",result:{failure:{code:"materials_missing"}},error:"reference 没有匹配版本材料，需先补知识/范例",model:null,usage:{},inputs:{}}]})
 await page.goto("/audits/task-1?stage=rules")
 await expect(page.getByText("请填写至少 10 个字符的规则目标")).toBeVisible()
 await expect(page.getByText("缺少匹配版本的参考材料或规则范例")).toBeVisible()
 await page.getByRole("link",{name:"补充知识材料"}).click();await expect(page).toHaveURL(/knowledge\?auditId=task-1/)
})
test("未通过验收不能发布；发布规则可用于新审计",async({page})=>{
 await mockAuditApi(page,{"/rules/":[rule]});await page.goto("/rules")
 await expect(page.getByText("独立测试：未运行")).toBeVisible()
 await expect(page.getByRole("button",{name:"发布此版本"})).toHaveCount(0)
 await page.unroute("**/api/v1/**");await mockAuditApi(page,{"/rules/":[{...rule,status:"published"}]});await page.reload()
 await page.getByRole("link",{name:"用于新审计"}).click();await expect(page).toHaveURL(/audits\/new\?ruleId=rule-1/)
})
