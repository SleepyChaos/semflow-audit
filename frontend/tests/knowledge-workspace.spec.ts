import {expect,test} from "@playwright/test"
import {mockAuditApi} from "./fixtures/audit-api"
const docs=[{document_id:"doc-1",title:"Flask API 参考",source:"pinned-source",language:"python",version:"abcdef",chunks:4,indexed_chunks:0,shared:false,index_error:null,corpus:"reference"},{document_id:"doc-2",title:"Express 查询范例",source:"pinned-example",language:"javascript",version:"xyz",chunks:2,indexed_chunks:0,shared:true,index_error:null,corpus:"rule_example"}]
test("知识列表和过滤可见，未向量化可用 BM25",async({page})=>{
 await mockAuditApi(page,{"/knowledge/":docs});await page.goto("/knowledge")
 await expect(page.getByRole("button",{name:"导入知识",exact:true})).toBeVisible()
 await expect(page.getByText("Flask API 参考")).toBeVisible()
 await expect(page.getByText("BM25 可用", {exact:false}).first()).toBeVisible()
 await page.getByLabel("知识语言").selectOption("javascript")
 await expect(page.getByText("Flask API 参考")).toHaveCount(0)
 await expect(page.getByText("Express 查询范例")).toBeVisible()
})
test("导入需要正文，来源 URL 仅作为引用，保存真实 provenance",async({page})=>{
 await mockAuditApi(page);await page.goto("/knowledge?auditId=task-1")
 await page.getByRole("button",{name:"导入知识",exact:true}).click()
 await page.getByLabel("资料标题").fill("Flask API reference")
 await page.getByLabel("来源或文档引用").fill("https://example.com/reference")
 await page.getByLabel("CodeQL语言库版本（规则生成按此过滤）").fill("4.0.10")
 await page.getByLabel("资料许可证").fill("MIT")
 await page.getByLabel("资料正文（不会自动访问来源网址）").fill("本材料说明 Flask GET 路由输入应先使用 escape 进行 HTML 转义，防止反射型 XSS。")
 const request=page.waitForRequest(r=>r.url().endsWith("/knowledge/")&&r.method()==="POST")
 await page.getByRole("button",{name:"保存知识",exact:true}).click()
 const body=(await request).postDataJSON()
 expect(body.language).toBe("python");expect(body.provenance).toEqual({api_version:"4.0.10",license:"MIT",trust:"user_supplied"});expect(body.content).toContain("HTML")
 await expect(page.getByRole("link",{name:"返回 RAG 规则"})).toBeVisible()
})
