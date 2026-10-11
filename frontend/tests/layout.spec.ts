import {expect,test} from "@playwright/test"
import {audit,mockAuditApi} from "./fixtures/audit-api"
for(const width of [1920,1366,375]){
 test(`工作台 ${width}px 无页面横向溢出`,async({page})=>{
  await page.setViewportSize({width,height:width===375?812:768})
  await mockAuditApi(page,{"/audits/":[{...audit,project_name:"超长项目名称".repeat(20)}]})
  for(const path of ["/","/audits","/audits/new","/knowledge","/rules","/audits/task-1?stage=review"]){
   await page.goto(path);await page.locator("h1").waitFor()
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),path).toBeTruthy()
  }
  if(width>700) await expect(page.getByRole("button",{name:"启动统一复核"})).toBeInViewport()
 })
}
