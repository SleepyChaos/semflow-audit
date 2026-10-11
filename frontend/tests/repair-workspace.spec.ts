import {expect,test} from "@playwright/test"
import {candidate,mockAuditApi} from "./fixtures/audit-api"
test("仅待确认候选可导出报告，但必须先确认再修复",async({page})=>{
 await mockAuditApi(page);await page.goto("/audits/task-1?stage=repair")
 await expect(page.getByRole("button",{name:"导出 Markdown 报告"})).toBeEnabled()
 await expect(page.getByRole("button",{name:"生成并验证修复 Diff"})).toBeDisabled()
 await expect(page.getByText("先确认缺陷")).toBeVisible()
 await page.getByRole("link",{name:"前往 AI 复审"}).click();await expect(page).toHaveURL(/stage=review/)
})
test("选择确认候选发送隔离验证选项和 ID",async({page})=>{
 await mockAuditApi(page,{"/audits/task-1/candidates":[{...candidate,status:"confirmed"}]})
 await page.goto("/audits/task-1?stage=repair")
 await page.getByRole("checkbox",{name:candidate.title,exact:true}).check()
 await expect(page.getByText("已选择 1 个已确认缺陷")).toBeVisible()
 const sent=page.waitForRequest(r=>r.url().endsWith("/task-1/repair")&&r.method()==="POST")
 await page.getByRole("button",{name:"生成并验证修复 Diff"}).click()
 expect((await sent).postDataJSON()).toEqual({candidate_ids:["candidate-1"],allowed_paths:[],validation_profile:"syntax",rescan:true})
})
